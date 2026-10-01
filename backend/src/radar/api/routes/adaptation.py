"""Profiles that follow their reader: what they learned, suggestions, impressions."""

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select

from radar.ai.factory import get_embedder
from radar.api.adapting import adapt_after_impressions, adapt_soon
from radar.api.deps import CacheDep, CurrentUser, SessionDep, user_rate_limit
from radar.api.routes.profiles import get_owned, profile_out, taste_changed
from radar.api.schemas import ProfileOut
from radar.db.models import (
    Article,
    InterestAdaptation,
    Profile,
    ProfileSuggestion,
    Source,
)
from radar.domain import Interest, ProfileSpec
from radar.recsys import store
from radar.recsys.adaptation import learned_for
from radar.recsys.model import adapted_weight
from radar.recsys.service import forget_taste
from radar.store.profiles import lock_profiles

router = APIRouter(tags=["adaptation"])

_write_limit = Depends(user_rate_limit("write", lambda settings: settings.rate_limit_per_minute))
_seen_limit = Depends(
    user_rate_limit("impressions", lambda settings: settings.feed_rate_limit_per_minute)
)
_EVIDENCE_SHOWN = 3
_MAX_INTERESTS = 20
_MAX_EXCLUSIONS = 20


class InterestLearning(BaseModel):
    interest_id: str
    title: str
    stated_weight: float
    weight: float
    factor: float
    drift: float
    positives: float
    negatives: float
    skipped: int


class EvidenceArticle(BaseModel):
    id: int
    title: str
    url: str
    source_name: str


class SuggestionOut(BaseModel):
    id: uuid.UUID
    kind: Literal["interest", "exclusion"]
    source: Literal["likes", "dislikes", "similar_readers"]
    title: str
    description: str
    keywords: list[str]
    articles: list[EvidenceArticle]
    created_at: datetime


class AdaptationOut(BaseModel):
    adaptive: bool
    # Marks before this moment do not count: the last reset.
    since: datetime | None
    updated_at: datetime | None
    interests: list[InterestLearning]
    suggestions: list[SuggestionOut]


class AdaptationIn(BaseModel):
    adaptive: bool


class ImpressionsIn(BaseModel):
    article_ids: list[int] = Field(min_length=1, max_length=60)
    context: Literal["feed", "digest"] = "feed"


async def _adaptation(session: SessionDep, user: CurrentUser, profile: Profile) -> AdaptationOut:
    spec = ProfileSpec.model_validate(profile.spec)
    model = get_embedder().model_id
    learned = await learned_for(session, user.id, profile.id, spec, model)
    updated_at = await session.scalar(
        select(func.max(InterestAdaptation.updated_at)).where(
            InterestAdaptation.profile_id == profile.id, InterestAdaptation.model == model
        )
    )
    rows = (
        (
            await session.execute(
                select(ProfileSuggestion)
                .where(
                    ProfileSuggestion.profile_id == profile.id, ProfileSuggestion.status == "open"
                )
                .order_by(ProfileSuggestion.created_at)
            )
        )
        .scalars()
        .all()
    )
    shown = {article_id for row in rows for article_id in row.article_ids[:_EVIDENCE_SHOWN]}
    articles = {
        article.id: EvidenceArticle(
            id=article.id, title=article.title, url=article.url, source_name=source_name
        )
        for article, source_name in (
            await session.execute(
                select(Article, Source.name)
                .join(Source, Source.id == Article.source_id)
                .where(Article.id.in_(sorted(shown)))
            )
        ).all()
    }
    return AdaptationOut(
        adaptive=profile.adaptive,
        since=profile.adapt_since,
        updated_at=updated_at if profile.adaptive else None,
        interests=[
            InterestLearning(
                interest_id=interest.id,
                title=interest.title,
                stated_weight=interest.weight,
                weight=round(adapted_weight(interest.weight, learned.get(interest.id)), 3),
                factor=own.factor if (own := learned.get(interest.id)) else 1.0,
                drift=own.drift if own else 0.0,
                positives=own.positives if own else 0.0,
                negatives=own.negatives if own else 0.0,
                skipped=own.skipped if own else 0,
            )
            for interest in spec.interests
        ],
        suggestions=[
            SuggestionOut(
                id=row.id,
                kind=row.kind,
                source=row.source,
                title=row.title,
                description=row.description,
                keywords=list(row.keywords),
                articles=[
                    articles[article_id]
                    for article_id in row.article_ids[:_EVIDENCE_SHOWN]
                    if article_id in articles
                ],
                created_at=row.created_at,
            )
            for row in rows
        ],
    )


@router.get("/profiles/{profile_id}/adaptation")
async def get_adaptation(
    profile_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> AdaptationOut:
    """What the profile learned from the reader's marks, and what it suggests."""
    return await _adaptation(session, user, await get_owned(session, user, profile_id))


@router.patch("/profiles/{profile_id}/adaptation", dependencies=[_write_limit])
async def set_adaptive(
    profile_id: uuid.UUID,
    payload: AdaptationIn,
    session: SessionDep,
    user: CurrentUser,
    cache: CacheDep,
) -> AdaptationOut:
    """Turn following the reader on or off. Off keeps what was learned, unused."""
    profile = await get_owned(session, user, profile_id)
    if profile.adaptive != payload.adaptive:
        profile.adaptive = payload.adaptive
        await session.commit()
        await forget_taste(cache, user.id)
        if payload.adaptive:
            await adapt_soon(user.id)
    return await _adaptation(session, user, profile)


@router.post("/profiles/{profile_id}/adaptation/reset", dependencies=[_write_limit])
async def reset_adaptation(
    profile_id: uuid.UUID, session: SessionDep, user: CurrentUser, cache: CacheDep
) -> AdaptationOut:
    """Forget what the profile learned; marks from now on teach it again."""
    # A recomputation running now finds the new start under the same lock
    # and does not write the old marks back.
    await lock_profiles(session, user.id)
    profile = await get_owned(session, user, profile_id)
    profile.adapt_since = datetime.now(UTC)
    await session.execute(
        delete(InterestAdaptation).where(InterestAdaptation.profile_id == profile.id)
    )
    await session.execute(
        delete(ProfileSuggestion).where(
            ProfileSuggestion.profile_id == profile.id, ProfileSuggestion.status == "open"
        )
    )
    await session.commit()
    await forget_taste(cache, user.id)
    return await _adaptation(session, user, profile)


async def _suggestion(
    session: SessionDep, profile: Profile, suggestion_id: uuid.UUID
) -> ProfileSuggestion:
    row = await session.scalar(
        select(ProfileSuggestion).where(
            ProfileSuggestion.id == suggestion_id,
            ProfileSuggestion.profile_id == profile.id,
            ProfileSuggestion.status == "open",
        )
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Предложение не найдено.")
    return row


def _applied(spec: ProfileSpec, suggestion: ProfileSuggestion) -> ProfileSpec:
    """The profile with the suggestion in it, validated like any edit."""
    data = spec.model_dump(mode="json")
    if suggestion.kind == "exclusion":
        if len(spec.exclusions) >= _MAX_EXCLUSIONS:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail="В профиле уже 20 исключений, удалите лишние."
            )
        data["exclusions"].append(suggestion.title)
    else:
        if len(spec.interests) >= _MAX_INTERESTS:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail="В профиле уже 20 интересов, удалите лишние."
            )
        interest = Interest(
            # The random tail of the id: the head is a timestamp, the same for
            # suggestions made within one millisecond.
            id=f"s-{suggestion.id.hex[-12:]}",
            title=suggestion.title,
            description=suggestion.description[:600],
            keywords=tuple(suggestion.keywords),
        )
        data["interests"].append(interest.model_dump(mode="json"))
    return ProfileSpec.model_validate(data)


@router.post(
    "/profiles/{profile_id}/suggestions/{suggestion_id}/accept", dependencies=[_write_limit]
)
async def accept_suggestion(
    profile_id: uuid.UUID,
    suggestion_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    cache: CacheDep,
) -> ProfileOut:
    """Add the suggested interest or exclusion: a new version of the profile."""
    await lock_profiles(session, user.id)
    profile = await get_owned(session, user, profile_id)
    suggestion = await _suggestion(session, profile, suggestion_id)
    spec = _applied(ProfileSpec.model_validate(profile.spec), suggestion)
    profile.spec = spec.model_dump(mode="json")
    profile.version += 1
    suggestion.status = "accepted"
    suggestion.decided_at = datetime.now(UTC)
    await session.flush()
    await session.refresh(profile)
    await taste_changed(session, cache, user.id)
    await adapt_soon(user.id)
    return profile_out(profile)


@router.post(
    "/profiles/{profile_id}/suggestions/{suggestion_id}/dismiss",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[_write_limit],
)
async def dismiss_suggestion(
    profile_id: uuid.UUID, suggestion_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> Response:
    """Not wanted: the same group of articles is not suggested again."""
    profile = await get_owned(session, user, profile_id)
    suggestion = await _suggestion(session, profile, suggestion_id)
    suggestion.status = "dismissed"
    suggestion.decided_at = datetime.now(UTC)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/impressions", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_seen_limit])
async def record_impressions(
    payload: ImpressionsIn, session: SessionDep, user: CurrentUser, cache: CacheDep
) -> Response:
    """Articles the reader has seen on screen, in the feed or in a digest."""
    if await store.record_impressions(session, user.id, payload.article_ids, payload.context):
        await session.commit()
        await adapt_after_impressions(cache, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
