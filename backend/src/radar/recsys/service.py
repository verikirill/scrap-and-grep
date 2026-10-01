"""Build a reader's taste and their feed from the database."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from radar.ai.embedder import Embedder
from radar.ai.factory import get_embedder
from radar.cache import Cache, get_cache
from radar.db import session_scope
from radar.db.models import Article, Profile, Resume, Source, User
from radar.domain import ProfileSpec
from radar.logging import get_logger
from radar.pipeline.ports import QueryEmbedder
from radar.pipeline.sql_store import CachedQueryEmbedder
from radar.reading import reading_minutes
from radar.recsys import store
from radar.recsys.adaptation import learned_interests
from radar.recsys.model import Personal, adapted_weight
from radar.recsys.ranking import (
    Evidence,
    Ranked,
    Weights,
    rerank_for_variety,
    score_article,
    with_exploration,
)
from radar.recsys.taste import Facet, Taste, build_taste
from radar.resume.extract import mentions
from radar.resume.model import STATUS_READY, ResumeFacts
from radar.selection.retrieval import exclusion_query, keyword_query
from radar.selection.scoring import retrieval_score
from radar.store.articles import load_vectors
from radar.text import tokenize, truncate

log = get_logger(__name__)

# The ranked list kept per reader; pages are slices of it.
FEED_SIZE = 120
# How long a built feed stays pageable. Pages are cut from one frozen list,
# so reactions between two pages do not reshuffle what comes next.
_SNAPSHOT_TTL = 1800
# A taste built while the embedding server was down has no vectors; it is
# kept only briefly, so the full one comes back soon after the server does.
_DEGRADED_TASTE_TTL = 60
# Scored candidates that go through the variety re-rank.
_RERANK_POOL = 240
_TASTE_TTL = 3600
_CORPUS_MEAN_TTL = 6 * 3600
_CORPUS_MEAN_DAYS = 30
_MAX_INTEREST_FACETS = 24
_RESUME_QUERY_SKILLS = 15
_SUMMARY_LIMIT = 320
# A part of the evidence is named as a reason when it is at least this strong.
_REASON_FROM = 0.45
_SOURCE_REASON_FROM = 0.15
# How far the reader's behaviour may move a digest score, up and down.
PERSONAL_GAIN = 0.2
PERSONAL_MAX_UP = 0.15
PERSONAL_MAX_DOWN = -0.2
# What a similarity equal to the period's average maps to (see retrieval_score).
_NEUTRAL_MATCH = retrieval_score(0.0, False)


class Reason(BaseModel):
    kind: str
    text: str


class FeedItem(BaseModel):
    article_id: int
    url: str
    title: str
    summary: str
    source_id: int
    source_name: str
    source_category: str
    language: str
    published_at: datetime
    score: float
    explore: bool = False
    reasons: list[Reason] = []
    parts: dict[str, float] = {}
    reactions: list[str] = []
    # Known once the full text has been read; None for a teaser.
    reading_minutes: int | None = None


class FacetOut(BaseModel):
    kind: str
    label: str
    weight: float


class SourceAffinity(BaseModel):
    source_id: int
    name: str
    affinity: float


class TasteOut(BaseModel):
    confidence: float
    positives: int
    negatives: int
    facets: list[FacetOut]
    sources: list[SourceAffinity]


@dataclass(frozen=True, slots=True)
class Reader:
    """A reader's taste with what else the feed needs to know about them."""

    taste: Taste
    exclusions: tuple[str, ...] = ()
    languages: tuple[str, ...] = ("ru", "en")
    skills: tuple[str, ...] = ()
    # True when the declared facets could not be embedded.
    degraded: bool = False


def _generation_key(user_id: uuid.UUID) -> str:
    return f"taste-generation:{user_id}"


async def _generation(cache: Cache, user_id: uuid.UUID) -> int:
    return await cache.get_int(_generation_key(user_id))


def _taste_key(user_id: uuid.UUID, model: str, generation: int) -> str:
    return f"taste:{user_id}:{model}:{generation}"


def _latest_feed_key(user_id: uuid.UUID, model: str, generation: int) -> str:
    return f"feed-latest:{user_id}:{model}:{generation}"


def _snapshot_key(user_id: uuid.UUID, snapshot: str) -> str:
    return f"feed-snapshot:{user_id}:{snapshot}"


async def forget_taste(cache: Cache, user_id: uuid.UUID) -> None:
    """Make the next request rebuild the taste and the feed from fresh input.

    Keys carry a per-reader generation number, and this moves it on. Deleting
    keys instead would race: a request that started before the change could
    finish after it and write the stale taste back under the same key. Now it
    writes under the old generation, which nobody reads any more.
    """
    await cache.incr(_generation_key(user_id))


def _dump(reader: Reader) -> dict[str, Any]:
    return {
        "facets": [
            {
                "key": facet.key,
                "kind": facet.kind,
                "label": facet.label,
                "weight": facet.weight,
                "query": facet.query,
                "vector": None if facet.vector is None else np.round(facet.vector, 5).tolist(),
            }
            for facet in reader.taste.facets
        ],
        "source_affinity": {str(key): value for key, value in reader.taste.source_affinity.items()},
        "reactions": {str(key): sorted(kinds) for key, kinds in reader.taste.reactions.items()},
        "rejected_ids": sorted(reader.taste.rejected_ids),
        "confidence": reader.taste.confidence,
        "positives": reader.taste.positives,
        "negatives": reader.taste.negatives,
        "exclusions": list(reader.exclusions),
        "languages": list(reader.languages),
        "skills": list(reader.skills),
    }


def _load(raw: dict[str, Any]) -> Reader:
    facets = tuple(
        Facet(
            key=item["key"],
            kind=item["kind"],
            label=item["label"],
            vector=None if item["vector"] is None else np.asarray(item["vector"], dtype=np.float32),
            weight=item["weight"],
            query=item["query"],
        )
        for item in raw["facets"]
    )
    taste = Taste(
        facets=facets,
        source_affinity={int(key): value for key, value in raw["source_affinity"].items()},
        reactions={int(key): frozenset(kinds) for key, kinds in raw["reactions"].items()},
        rejected_ids=frozenset(raw["rejected_ids"]),
        confidence=raw["confidence"],
        positives=raw["positives"],
        negatives=raw["negatives"],
    )
    return Reader(
        taste=taste,
        exclusions=tuple(raw["exclusions"]),
        languages=tuple(raw["languages"]),
        skills=tuple(raw["skills"]),
    )


async def _declared(
    session: AsyncSession, user_id: uuid.UUID, embed_queries: QueryEmbedder, model: str
) -> tuple[list[Facet], tuple[str, ...], tuple[str, ...], tuple[str, ...], bool]:
    """Facets the reader stated: interests of every profile and the resume.

    The last value is True when the facets could not be embedded.
    """
    profiles = (
        (
            await session.execute(
                select(Profile)
                .where(Profile.user_id == user_id)
                .order_by(Profile.created_at, Profile.id)
            )
        )
        .scalars()
        .all()
    )
    specs = [ProfileSpec.model_validate(profile.spec) for profile in profiles]
    # Adaptive profiles bring their interests as the reader's marks shaped
    # them: weighted by how well each one does, searching where the liked
    # articles were.
    learned = await learned_interests(session, profiles, model)
    moved: dict[str, list[float]] = {}
    # The same interest in two profiles is one facet, with the higher weight.
    interests: dict[str, tuple[str, Facet]] = {}
    for profile, spec in zip(profiles, specs, strict=True):
        for interest in spec.interests:
            text = interest.as_query()
            own = learned.get((profile.id, interest.id))
            weight = adapted_weight(interest.weight, own)
            known = interests.get(text)
            if known is not None and known[1].weight >= weight:
                continue
            if own is not None and own.vector is not None:
                moved[text] = own.vector
            else:
                moved.pop(text, None)
            interests[text] = (
                text,
                Facet(
                    key=f"interest:{interest.id}",
                    kind="interest",
                    label=interest.title,
                    weight=weight,
                    query=keyword_query(interest.keywords or (interest.title,)),
                ),
            )
    declared = list(interests.values())[:_MAX_INTEREST_FACETS]
    # Two profiles may reuse an interest id for different content.
    seen: dict[str, int] = {}
    for index, (text, facet) in enumerate(declared):
        count = seen.get(facet.key, 0)
        seen[facet.key] = count + 1
        if count:
            declared[index] = (
                text,
                Facet(
                    f"{facet.key}#{count}", facet.kind, facet.label, None, facet.weight, facet.query
                ),
            )

    skills: tuple[str, ...] = ()
    resume = (
        await session.execute(
            select(Resume.facts).where(Resume.user_id == user_id, Resume.status == STATUS_READY)
        )
    ).scalar_one_or_none()
    if resume:
        facts = ResumeFacts.model_validate(resume)
        skills = facts.skills
        declared.append(
            (
                facts.as_query(),
                Facet(
                    key="resume",
                    kind="resume",
                    label=facts.headline,
                    query=keyword_query(facts.skills[:_RESUME_QUERY_SKILLS]),
                ),
            )
        )

    vectors: list[list[float]] | None
    try:
        vectors = await embed_queries([text for text, _ in declared]) if declared else []
    except Exception as exc:
        # The embedding server is down: facets keep their keywords and the
        # feed degrades to full-text matching.
        log.warning("taste_embedding_failed", error=f"{type(exc).__name__}: {exc}"[:200])
        vectors = None
    facets = [
        Facet(
            facet.key,
            facet.kind,
            facet.label,
            np.asarray(moved.get(text, vectors[index]), dtype=np.float32)
            if vectors is not None
            else None,
            facet.weight,
            facet.query,
        )
        for index, (text, facet) in enumerate(declared)
    ]
    exclusions = tuple(
        dict.fromkeys(
            query for spec in specs for item in spec.exclusions if (query := exclusion_query(item))
        )
    )
    languages = tuple(dict.fromkeys(lang for spec in specs for lang in spec.languages))
    return facets, exclusions, languages or ("ru", "en"), skills, vectors is None


async def load_reader(
    session: AsyncSession,
    cache: Cache,
    user_id: uuid.UUID,
    *,
    embedder: Embedder | None = None,
    embed_queries: QueryEmbedder | None = None,
) -> Reader:
    """The reader's taste, from cache or rebuilt from profiles, resume and signals."""
    embedder = embedder or get_embedder()
    # Read the generation before the data: see forget_taste.
    key = _taste_key(user_id, embedder.model_id, await _generation(cache, user_id))
    cached = await cache.get_json(key)
    if cached is not None:
        return _load(cached)
    embed_queries = embed_queries or CachedQueryEmbedder(embedder, cache)
    facets, exclusions, languages, skills, degraded = await _declared(
        session, user_id, embed_queries, embedder.model_id
    )
    signals = await store.load_signals(session, user_id, embedder.model_id)
    rejected = await store.rejected_ids(session, user_id)
    reader = Reader(
        taste=build_taste(facets, signals, rejected),
        exclusions=exclusions,
        languages=languages,
        skills=skills,
        degraded=degraded,
    )
    await cache.set_json(key, _dump(reader), _DEGRADED_TASTE_TTL if degraded else _TASTE_TTL)
    return reader


def _reasons(
    ranked: Ranked,
    reader: Reader,
    article: Article,
    source_name: str,
) -> list[Reason]:
    if ranked.explore:
        return [Reason(kind="explore", text="Что-то новое для вас")]
    if not ranked.parts:
        # Listed, not ranked: a saved article has no score to explain.
        return []
    labels = {facet.key: facet.label for facet in reader.taste.facets}
    parts = ranked.parts
    reasons: list[tuple[float, Reason]] = []
    if parts["interest"] >= _REASON_FROM and "interest" in ranked.best:
        label = labels[ranked.best["interest"]]
        reasons.append((parts["interest"], Reason(kind="interest", text=f"Интерес «{label}»")))
    if parts["resume"] >= _REASON_FROM and "resume" in ranked.best:
        tokens = tokenize(f"{article.title} {article.summary}")
        found = [skill for skill in reader.skills if mentions(skill, tokens)][:3]
        text = f"Из резюме: {', '.join(found)}" if found else "Близко к опыту из резюме"
        reasons.append((parts["resume"], Reason(kind="resume", text=text)))
    if parts["learned"] >= _REASON_FROM and "learned" in ranked.best:
        label = truncate(labels[ranked.best["learned"]], 70)
        reasons.append(
            (
                parts["learned"] * reader.taste.confidence,
                Reason(kind="learned", text=f"Похоже на «{label}», которое вы отметили"),
            )
        )
    ordered = [reason for _, reason in sorted(reasons, key=lambda item: -item[0])]
    if parts["collab"] > 0:
        ordered.append(Reason(kind="collab", text="Читают коллеги с похожим профилем"))
    if reader.taste.source_affinity.get(article.source_id, 0.0) >= _SOURCE_REASON_FROM:
        ordered.append(Reason(kind="source", text=f"Вы часто отмечаете «{source_name}»"))
    return ordered[:3]


async def _cards(session: AsyncSession, ranked: Sequence[Ranked], reader: Reader) -> list[FeedItem]:
    ids = [item.article_id for item in ranked]
    if not ids:
        return []
    rows = await session.execute(
        select(Article, Source.name, Source.category)
        .join(Source, Source.id == Article.source_id)
        .where(Article.id.in_(ids))
    )
    found = {article.id: (article, name, category) for article, name, category in rows.all()}
    items = []
    for entry in ranked:
        if entry.article_id not in found:
            continue
        article, source_name, category = found[entry.article_id]
        items.append(
            FeedItem(
                article_id=article.id,
                url=article.url,
                title=article.title,
                summary=truncate(article.summary, _SUMMARY_LIMIT),
                source_id=article.source_id,
                source_name=source_name,
                source_category=category,
                language=article.language,
                published_at=article.published_at,
                score=round(entry.score, 3),
                explore=entry.explore,
                reasons=_reasons(entry, reader, article, source_name),
                parts=entry.parts,
                reading_minutes=reading_minutes(article.word_count, article.language),
            )
        )
    return items


def _rank(
    evidence: Sequence[Evidence],
    reader: Reader,
    weights: Weights,
    *,
    semantic: bool,
) -> list[Ranked]:
    taste = reader.taste
    return [
        score_article(
            item,
            taste,
            weights,
            semantic=semantic,
            read="open" in taste.reactions.get(item.article_id, frozenset()),
        )
        for item in evidence
    ]


async def build_feed(
    session: AsyncSession,
    cache: Cache,
    user_id: uuid.UUID,
    *,
    window_days: int,
    weights: Weights | None = None,
    embedder: Embedder | None = None,
) -> list[FeedItem]:
    """Rank the period's articles for one reader."""
    weights = weights or Weights()
    embedder = embedder or get_embedder()
    reader = await load_reader(session, cache, user_id, embedder=embedder)
    taste = reader.taste
    now = datetime.now(UTC)
    scope = store.Scope(
        start=now - timedelta(days=window_days),
        end=now + timedelta(minutes=5),
        languages=reader.languages,
        exclusions=reader.exclusions,
        skip=tuple(sorted(taste.rejected_ids)),
    )
    evidence = await store.evidence(
        session, model=embedder.model_id, scope=scope, facets=taste.facets
    )
    if not any(facet.kind != "avoid" for facet in taste.facets):
        # Nothing is known about the reader yet: show what is new.
        newest = sorted(evidence, key=lambda item: item.age_hours)[:FEED_SIZE]
        ranked = [Ranked(item.article_id, 0.0, {}, {}, explore=True) for item in newest]
        return await _cards(session, ranked, reader)

    shared = await store.collab(
        session, user_id, embedder.model_id, [item.article_id for item in evidence]
    )
    evidence = [
        Evidence(
            item.article_id,
            item.source_id,
            item.age_hours,
            item.z,
            item.rank_share,
            shared.get(item.article_id, 0.0),
        )
        for item in evidence
    ]
    ranked = _rank(evidence, reader, weights, semantic=embedder.semantic)
    chosen = sorted(
        (item for item in ranked if item.score >= weights.min_score),
        key=lambda item: (-item.score, item.article_id),
    )[:_RERANK_POOL]
    spare = [item for item in ranked if item.score < weights.min_score]
    vectors = await load_vectors(session, embedder.model_id, [item.article_id for item in chosen])
    sources = {item.article_id: item.source_id for item in evidence}
    feed = rerank_for_variety(
        chosen,
        vectors,
        sources,
        duplicate_threshold=embedder.duplicate_threshold,
        variety=weights.variety,
        limit=FEED_SIZE,
    )
    feed = with_exploration(feed, spare, seed=f"{user_id}:{now:%Y-%m-%d}", limit=FEED_SIZE)
    return await _cards(session, feed, reader)


async def feed_page(
    session: AsyncSession,
    cache: Cache,
    user_id: uuid.UUID,
    *,
    window_days: int,
    ttl: int,
    limit: int,
    offset: int,
    snapshot: str | None = None,
) -> tuple[list[FeedItem], int, str]:
    """One page of the reader's feed, with their current reactions attached.

    The first page builds (or reuses, for `ttl` seconds) a ranked list and
    names it; later pages ask for the same snapshot, so a like between two
    pages cannot make an article appear twice or never. Returns the page, the
    length of the list and the snapshot id.
    """
    items: list[FeedItem] | None = None
    if snapshot is not None:
        stored = await cache.get_json(_snapshot_key(user_id, snapshot))
        if stored is not None:
            items = [FeedItem.model_validate(item) for item in stored]
    model = get_embedder().model_id
    latest_key = _latest_feed_key(user_id, model, await _generation(cache, user_id))
    if items is None:
        latest = await cache.get_json(latest_key)
        if latest is not None:
            stored = await cache.get_json(_snapshot_key(user_id, latest))
            if stored is not None:
                items, snapshot = [FeedItem.model_validate(item) for item in stored], latest
    if items is None or snapshot is None:
        items = await build_feed(session, cache, user_id, window_days=window_days)
        snapshot = uuid.uuid4().hex
        await cache.set_json(
            _snapshot_key(user_id, snapshot),
            [item.model_dump(mode="json") for item in items],
            _SNAPSHOT_TTL,
        )
        await cache.set_json(latest_key, snapshot, ttl)
    page = items[offset : offset + limit]
    # Reactions are read live: the snapshot may be half an hour old.
    current = await store.reactions(session, user_id, [item.article_id for item in page])
    return (
        [
            item.model_copy(update={"reactions": sorted(current.get(item.article_id, []))})
            for item in page
        ],
        len(items),
        snapshot,
    )


async def saved_page(
    session: AsyncSession, user_id: uuid.UUID, *, limit: int, offset: int
) -> tuple[list[FeedItem], int]:
    ids, total = await store.saved_ids(session, user_id, limit, offset)
    ranked = [Ranked(article_id, 0.0, {}, {}) for article_id in ids]
    cards = await _cards(session, ranked, Reader(taste=Taste()))
    current = await store.reactions(session, user_id, ids)
    return (
        [
            card.model_copy(update={"reactions": sorted(current.get(card.article_id, []))})
            for card in cards
        ],
        total,
    )


async def taste_summary(session: AsyncSession, cache: Cache, user_id: uuid.UUID) -> TasteOut:
    reader = await load_reader(session, cache, user_id)
    taste = reader.taste
    ranked_sources = sorted(taste.source_affinity.items(), key=lambda item: -abs(item[1]))[:8]
    names = dict(
        (
            await session.execute(
                select(Source.id, Source.name).where(
                    Source.id.in_([source_id for source_id, _ in ranked_sources])
                )
            )
        ).all()
    )
    return TasteOut(
        confidence=round(taste.confidence, 3),
        positives=taste.positives,
        negatives=taste.negatives,
        facets=[
            FacetOut(kind=facet.kind, label=facet.label, weight=round(facet.weight, 3))
            for facet in taste.facets
        ],
        sources=[
            SourceAffinity(source_id=source_id, name=names[source_id], affinity=round(value, 3))
            for source_id, value in ranked_sources
            if source_id in names
        ],
    )


async def personal_adjustments(
    user_id: uuid.UUID,
    article_ids: Sequence[int],
    start: datetime,
    end: datetime,
    *,
    weights: Weights | None = None,
    cache: Cache | None = None,
) -> dict[int, Personal]:
    """How the reader's behaviour moves the digest candidates.

    Stated interests are already in the digest score; this adds what the
    profile cannot say: themes learned from likes, rejected themes, source
    preferences and what readers alike picked.
    """
    weights = weights or Weights()
    cache = cache or get_cache()
    embedder = get_embedder()
    async with session_scope() as session:
        reader = await load_reader(session, cache, user_id, embedder=embedder)
        taste = reader.taste
        behaviour = [facet for facet in taste.facets if facet.kind in ("learned", "avoid")]
        rejected = {article_id for article_id in article_ids if taste.rejected(article_id)}
        if not behaviour and not taste.source_affinity:
            return {article_id: Personal(rejected=True) for article_id in rejected}
        evidence = await store.evidence(
            session,
            model=embedder.model_id,
            scope=store.Scope(start=start, end=end, languages=("ru", "en")),
            facets=behaviour,
            include=list(article_ids),
        )
        shared = await store.collab(session, user_id, embedder.model_id, list(article_ids))

    labels = {facet.key: facet.label for facet in behaviour}
    behaviour_taste = Taste(
        facets=tuple(behaviour),
        source_affinity=taste.source_affinity,
        confidence=taste.confidence,
    )
    result = {article_id: Personal(rejected=True) for article_id in rejected}
    for item in evidence:
        if item.article_id in rejected:
            continue
        item = Evidence(
            item.article_id,
            item.source_id,
            item.age_hours,
            item.z,
            item.rank_share,
            shared.get(item.article_id, 0.0),
        )
        ranked = score_article(item, behaviour_taste, weights, semantic=embedder.semantic)
        parts = ranked.parts
        learned = (
            PERSONAL_GAIN * taste.confidence * (parts["learned"] - _NEUTRAL_MATCH)
            if "learned" in ranked.best
            else 0.0
        )
        delta = learned + parts["source"] + parts["collab"] + parts["avoid"]
        delta = float(min(PERSONAL_MAX_UP, max(PERSONAL_MAX_DOWN, delta)))
        if abs(delta) < 0.005:
            continue
        note = ""
        if parts["avoid"] < 0 and abs(parts["avoid"]) > abs(learned):
            note = "близко к тому, что вы скрыли"
        elif learned > 0 and "learned" in ranked.best:
            note = f"похоже на отмеченное «{truncate(labels[ranked.best['learned']], 60)}»"
        result[item.article_id] = Personal(delta=round(delta, 3), note=note)
    return result


async def store_taste_vector(user_id: uuid.UUID) -> None:
    """Persist the reader's taste as one vector, for finding readers alike.

    Guests are left out: their clicks are throwaway. So is a taste built
    while the embedding server was down, which would erase a good vector.
    """
    cache = get_cache()
    embedder = get_embedder()
    mean_key = f"corpus-mean:{embedder.model_id}"
    async with session_scope() as session:
        is_demo = await session.scalar(select(User.is_demo).where(User.id == user_id))
        if is_demo is None or is_demo:
            return
        reader = await load_reader(session, cache, user_id, embedder=embedder)
        if reader.degraded:
            return
        centroid = reader.taste.centroid()
        vector: np.ndarray | None = None
        if centroid is not None:
            cached = await cache.get_json(mean_key)
            if cached is None:
                since = datetime.now(UTC) - timedelta(days=_CORPUS_MEAN_DAYS)
                mean = await store.corpus_mean(session, embedder.model_id, since)
                if mean is not None:
                    await cache.set_json(mean_key, mean.tolist(), _CORPUS_MEAN_TTL)
            else:
                mean = np.asarray(cached, dtype=np.float32)
            centred = centroid - mean if mean is not None else centroid
            norm = float(np.linalg.norm(centred))
            vector = centred / norm if norm > 1e-6 else None
        await store.save_user_vector(session, user_id, embedder.model_id, vector)
