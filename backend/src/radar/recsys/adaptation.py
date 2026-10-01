"""Profiles that follow their reader: from marks to weights, meaning and suggestions.

The reader's marks and the articles they scrolled past are matched to the
interests of every adaptive profile the way digest retrieval would match them.
Each interest then gets a weight factor and, with enough likes, a search vector
turned towards what was liked (recsys.adapt). Liked articles no interest
would have found, and articles readers alike liked, become suggested new
interests; groups of rejected articles become suggested exclusions.
"""

import math
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from radar.ai.embedder import Embedder
from radar.ai.factory import get_embedder
from radar.cache import Cache, get_cache
from radar.db import session_scope
from radar.db.models import Article, InterestAdaptation, Profile, ProfileSuggestion
from radar.domain import Interest, ProfileSpec
from radar.logging import get_logger
from radar.pipeline.sql_store import CachedQueryEmbedder
from radar.recsys import store
from radar.recsys.adapt import InterestState, adapt_interest, groups_of, skip_ages, title_key
from radar.recsys.model import Learned
from radar.recsys.naming import exclusion_phrase, name_interest
from radar.recsys.ranking import Evidence
from radar.recsys.taste import Facet, Signal, net_weights
from radar.selection.retrieval import keyword_query
from radar.selection.scoring import lexical_score, retrieval_score
from radar.store.articles import load_vectors
from radar.store.profiles import lock_profiles
from radar.text import stable_hash, tokenize

log = get_logger(__name__)

# An article counts under an interest when the interest's own retrieval would
# score it this high, and the profile "already covers" it from the digest
# threshold up.
ATTRIBUTE_FROM = 0.45
COVERED_FROM = 0.5
# Similarities are compared with the articles of this many recent days.
SCOPE_DAYS = 60
SUGGESTION_GROUP = 3
MAX_OPEN_SUGGESTIONS = 3
# A group that shares this part of its articles with an earlier suggestion,
# open, accepted or dismissed, is the same suggestion again.
SAME_SUGGESTION = 0.5
# Suggestions named by the model in one run; the rest wait for the next run.
NAMING_PER_RUN = 3


def interest_hash(interest: Interest) -> str:
    """Changes when the interest's text changes, which voids what it learned."""
    return stable_hash(interest.as_query())


def _match(item: Evidence, keys: Sequence[str], *, semantic: bool) -> tuple[str | None, float]:
    """The interest that would bring the article in, and how strongly."""
    best: str | None = None
    top = 0.0
    for key in keys:
        z = item.z.get(key, 0.0)
        lexical = key in item.rank_share
        score = (
            retrieval_score(z, lexical)
            if semantic
            else lexical_score(item.rank_share.get(key, 0.0), z, lexical)
        )
        if score > top:
            best, top = key, score
    return best, top


@dataclass(frozen=True, slots=True)
class _Pending:
    """A group of articles that may become a suggestion."""

    kind: str
    source: str
    article_ids: tuple[int, ...]
    titles: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ProfileWork:
    """What one profile learned, computed from a read of it, not yet written."""

    profile_id: uuid.UUID
    # The profile as it was read: a reset or an edit since voids this work.
    adapt_since: datetime | None
    version: int
    hashes: dict[str, str]
    states: tuple[InterestState, ...]
    known_words: tuple[str, ...]
    exclusions: tuple[str, ...]
    # Interest titles: a suggestion named like one of them is not a new subject.
    titles: tuple[str, ...]
    pending: tuple[_Pending, ...]


async def _alike_signals(
    session: AsyncSession, model: str, alike: dict[int, float], skip: set[int]
) -> list[tuple[float, Signal]]:
    ids = [article_id for article_id in alike if article_id not in skip]
    if not ids:
        return []
    vectors = await load_vectors(session, model, ids)
    rows = await session.execute(
        select(Article.id, Article.source_id, Article.title).where(Article.id.in_(ids))
    )
    return [
        (
            alike[article_id],
            Signal(article_id, "like", 0.0, source_id, title, vectors.get(article_id)),
        )
        for article_id, source_id, title in rows.all()
    ]


async def _learn(
    session: AsyncSession,
    profile: Profile,
    *,
    signals: Sequence[Signal],
    seen: dict[int, tuple[int, datetime]],
    reacted: set[int],
    alike: dict[int, float],
    embedder: Embedder,
    embed_queries: CachedQueryEmbedder,
    now: datetime,
) -> _ProfileWork | None:
    """Compute what the profile learned. Reads only."""
    spec = ProfileSpec.model_validate(profile.spec)
    window = (
        (now - profile.adapt_since).total_seconds() / 86400 if profile.adapt_since else math.inf
    )
    marks = [signal for signal in signals if signal.age_days <= window]
    skipped = {
        article_id: (times, (now - last).total_seconds() / 86400)
        for article_id, (times, last) in seen.items()
        if article_id not in reacted and (now - last).total_seconds() / 86400 <= window
    }
    try:
        vectors = await embed_queries([interest.as_query() for interest in spec.interests])
    except Exception as exc:
        # Without the interests' vectors nothing can be matched; the old state stays.
        log.warning("adaptation_embedding_failed", error=f"{type(exc).__name__}: {exc}"[:200])
        return None
    facets = [
        Facet(
            key=interest.id,
            kind="interest",
            label=interest.title,
            vector=np.asarray(vector, dtype=np.float32),
            weight=interest.weight,
            query=keyword_query(interest.keywords or (interest.title,)),
        )
        for interest, vector in zip(spec.interests, vectors, strict=True)
    ]
    ids = {signal.article_id for signal in marks} | set(skipped) | set(alike)
    evidence = (
        await store.evidence(
            session,
            model=embedder.model_id,
            scope=store.Scope(
                start=now - timedelta(days=SCOPE_DAYS),
                end=now + timedelta(minutes=5),
                languages=spec.languages,
            ),
            facets=facets,
            include=sorted(ids),
        )
        if ids
        else []
    )
    keys = [facet.key for facet in facets]
    # Only articles of the period and of the profile's languages get a match;
    # the rest cannot be judged and take no part below, rather than passing
    # for "no interest covers this".
    matches = {item.article_id: _match(item, keys, semantic=embedder.semantic) for item in evidence}

    def owner(article_id: int) -> str | None:
        key, score = matches.get(article_id, (None, 0.0))
        return key if score >= ATTRIBUTE_FROM else None

    states = tuple(
        adapt_interest(
            facet.key,
            facet.vector,
            [signal for signal in marks if owner(signal.article_id) == facet.key],
            skip_ages(
                (times, age)
                for article_id, (times, age) in skipped.items()
                if owner(article_id) == facet.key
            ),
        )
        for facet in facets
    )

    net = net_weights(marks)
    uncovered = {article_id for article_id, (_, score) in matches.items() if score < COVERED_FROM}
    liked = [
        (weight, signal)
        for weight, signal in net.values()
        if weight > 0 and signal.article_id in uncovered
    ]
    rejected = [
        (-weight, signal)
        for weight, signal in net.values()
        if weight < 0 and signal.article_id in matches
    ]
    from_alike = [
        item
        for item in await _alike_signals(session, embedder.model_id, alike, set(net))
        if item[1].article_id in uncovered
    ]
    pending = tuple(
        _Pending(kind, source, tuple(s.article_id for s in group), tuple(s.title for s in group))
        for kind, source, weighted in (
            ("interest", "likes", liked),
            ("interest", "similar_readers", from_alike),
            ("exclusion", "dislikes", rejected),
        )
        for group in groups_of(weighted, min_size=SUGGESTION_GROUP)
    )
    return _ProfileWork(
        profile_id=profile.id,
        adapt_since=profile.adapt_since,
        version=profile.version,
        hashes={interest.id: interest_hash(interest) for interest in spec.interests},
        states=states,
        known_words=tuple(
            word
            for interest in spec.interests
            for text in (interest.title, *interest.keywords)
            for word in tokenize(text)
        ),
        exclusions=spec.exclusions,
        titles=tuple(interest.title for interest in spec.interests),
        pending=pending,
    )


async def _still_current(session: AsyncSession, work: _ProfileWork) -> bool:
    """Is the profile as it was read: there, adaptive, not reset, not edited?"""
    profile = await session.get(Profile, work.profile_id, populate_existing=True)
    return (
        profile is not None
        and profile.adaptive
        and profile.adapt_since == work.adapt_since
        and profile.version == work.version
    )


async def _write(session: AsyncSession, work: _ProfileWork, model: str) -> None:
    await session.execute(
        delete(InterestAdaptation).where(
            InterestAdaptation.profile_id == work.profile_id, InterestAdaptation.model == model
        )
    )
    session.add_all(
        InterestAdaptation(
            profile_id=work.profile_id,
            interest_id=state.interest_id,
            model=model,
            base_hash=work.hashes[state.interest_id],
            factor=state.factor,
            vector=None if state.vector is None else state.vector.tolist(),
            drift=state.drift,
            positives=state.positives,
            negatives=state.negatives,
            skipped=state.skipped,
        )
        for state in work.states
    )


def _overlaps(article_ids: Sequence[int], earlier: Sequence[Sequence[int]]) -> bool:
    mine = set(article_ids)
    return any(
        len(mine & set(other)) >= SAME_SUGGESTION * min(len(mine), len(other))
        for other in earlier
        if other
    )


async def _suggest(user_id: uuid.UUID, work: _ProfileWork, budget: int) -> int:
    """Name the new groups and store them, a few open suggestions at a time.

    Returns how many names the model was asked for: one run asks at most
    `budget` times, the rest waits for the next run.
    """
    async with session_scope() as session:
        rows = (
            await session.execute(
                select(
                    ProfileSuggestion.article_ids,
                    ProfileSuggestion.status,
                    ProfileSuggestion.title,
                ).where(ProfileSuggestion.profile_id == work.profile_id)
            )
        ).all()
    earlier = [list(ids) for ids, _, _ in rows]
    # Two groups of articles can get one name; one suggestion per name, and
    # none named like an interest the profile already has.
    names = {title_key(title) for title in (*work.titles, *(title for _, _, title in rows))}
    room = MAX_OPEN_SUGGESTIONS - sum(1 for _, status, _ in rows if status == "open")
    fresh: list[ProfileSuggestion] = []
    asked = 0
    for group in work.pending:
        if room <= 0:
            break
        if _overlaps(group.article_ids, earlier):
            continue
        status = "open"
        if group.kind == "exclusion":
            phrase = exclusion_phrase(group.titles, known=work.known_words)
            if phrase is None or phrase.lower() in (item.lower() for item in work.exclusions):
                continue
            title, description, keywords = phrase, "", [phrase]
        else:
            if asked >= budget:
                continue
            asked += 1
            draft = await name_interest(group.titles, known=work.known_words)
            title, description, keywords = draft.title, draft.description, list(draft.keywords)
            if title_key(title) in names:
                # Kept, but not shown: the same articles are not named again
                # on every run.
                status = "duplicate"
            names.add(title_key(title))
        fresh.append(
            ProfileSuggestion(
                profile_id=work.profile_id,
                kind=group.kind,
                source=group.source,
                title=title,
                description=description,
                keywords=keywords,
                article_ids=list(group.article_ids),
                status=status,
            )
        )
        earlier.append(list(group.article_ids))
        room -= status == "open"
    if not fresh:
        return asked
    async with session_scope() as session:
        await lock_profiles(session, user_id)
        # A reset, an edit or an accept while the names were being written:
        # these groups were found in a profile that is no longer there.
        if not await _still_current(session, work):
            return asked
        taken = (
            await session.execute(
                select(ProfileSuggestion.article_ids).where(
                    ProfileSuggestion.profile_id == work.profile_id
                )
            )
        ).scalars()
        known = [list(ids) for ids in taken]
        session.add_all(item for item in fresh if not _overlaps(item.article_ids, known))
    return asked


async def adapt_reader(user_id: uuid.UUID, *, cache: Cache | None = None) -> int:
    """Recompute every adaptive profile of the reader. Returns how many were updated."""
    cache = cache or get_cache()
    embedder = get_embedder()
    embed_queries = CachedQueryEmbedder(embedder, cache)
    now = datetime.now(UTC)
    work: list[_ProfileWork] = []
    async with session_scope() as session:
        profiles = (
            (
                await session.execute(
                    select(Profile)
                    .where(Profile.user_id == user_id, Profile.adaptive)
                    .order_by(Profile.created_at, Profile.id)
                )
            )
            .scalars()
            .all()
        )
        if not profiles:
            return 0
        signals = await store.load_signals(session, user_id, embedder.model_id)
        seen = await store.seen_since(session, user_id, now - timedelta(days=SCOPE_DAYS))
        reacted = set(await store.reactions(session, user_id, list(seen)))
        alike = await store.liked_by_readers_alike(session, user_id, embedder.model_id)
        for profile in profiles:
            learned = await _learn(
                session,
                profile,
                signals=signals,
                seen=seen,
                reacted=reacted,
                alike=alike,
                embedder=embedder,
                embed_queries=embed_queries,
                now=now,
            )
            if learned is not None:
                work.append(learned)

    # Written under the same lock as a reset or an accept, and only for a
    # profile still as it was read: what was learned from the old marks must
    # not land on a profile reset meanwhile.
    written: list[_ProfileWork] = []
    async with session_scope() as session:
        await lock_profiles(session, user_id)
        for item in work:
            if await _still_current(session, item):
                await _write(session, item, embedder.model_id)
                written.append(item)

    # Naming may call the model: no database connection is held meanwhile.
    budget = NAMING_PER_RUN
    for item in written:
        try:
            budget -= await _suggest(user_id, item, budget)
        except Exception as exc:
            # The learned weights and meaning are saved; suggestions come next time.
            log.warning("suggestions_failed", error=f"{type(exc).__name__}: {exc}"[:200])
    # Imported here: the feed service imports this module's neighbours.
    from radar.recsys.service import forget_taste

    await forget_taste(cache, user_id)
    return len(written)


async def learned_interests(
    session: AsyncSession, profiles: Sequence[Profile], model: str
) -> dict[tuple[uuid.UUID, str], Learned]:
    """What the interests of the adaptive ones among `profiles` learned.

    An interest whose text changed since gets nothing: the old meaning moved
    is not the new one.
    """
    adaptive = {profile.id: profile for profile in profiles if profile.adaptive}
    if not adaptive:
        return {}
    rows = (
        await session.execute(
            select(InterestAdaptation).where(
                InterestAdaptation.profile_id.in_(list(adaptive)),
                InterestAdaptation.model == model,
            )
        )
    ).scalars()
    hashes = {
        (profile.id, interest.id): interest_hash(interest)
        for profile in adaptive.values()
        for interest in ProfileSpec.model_validate(profile.spec).interests
    }
    return {
        (row.profile_id, row.interest_id): _learned(row)
        for row in rows
        if hashes.get((row.profile_id, row.interest_id)) == row.base_hash
    }


async def learned_for(
    session: AsyncSession, user_id: uuid.UUID, profile_id: uuid.UUID, spec: ProfileSpec, model: str
) -> dict[str, Learned]:
    """What the reader's profile learned, matched against `spec`: the snapshot a
    digest was ordered with, which may be older than the profile now."""
    profile = await session.scalar(
        select(Profile).where(Profile.id == profile_id, Profile.user_id == user_id)
    )
    if profile is None or not profile.adaptive:
        return {}
    hashes = {interest.id: interest_hash(interest) for interest in spec.interests}
    rows = (
        await session.execute(
            select(InterestAdaptation).where(
                InterestAdaptation.profile_id == profile_id, InterestAdaptation.model == model
            )
        )
    ).scalars()
    return {
        row.interest_id: _learned(row)
        for row in rows
        if hashes.get(row.interest_id) == row.base_hash
    }


def _learned(row: InterestAdaptation) -> Learned:
    return Learned(
        factor=row.factor,
        vector=None if row.vector is None else [float(value) for value in row.vector],
        drift=row.drift,
        positives=row.positives,
        negatives=row.negatives,
        skipped=row.skipped,
    )
