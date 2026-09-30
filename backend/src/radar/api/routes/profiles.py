"""Reader profiles and the instant selection preview."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select

from radar.ai.factory import get_embedder
from radar.api.deps import CacheDep, SessionDep, SettingsDep, rate_limit
from radar.api.schemas import PreviewItem, PreviewOut, PreviewRequest, ProfileOut
from radar.db.models import Profile
from radar.domain import ProfileSpec
from radar.pipeline.sql_store import CachedQueryEmbedder
from radar.selection.preview import build_preview

router = APIRouter(tags=["profiles"])

_write_limit = Depends(rate_limit("write", lambda settings: settings.rate_limit_per_minute))
_preview_limit = Depends(rate_limit("preview", lambda settings: settings.rate_limit_per_minute))

PREVIEW_ITEMS = 60
# Round the window to this many minutes so that repeated previews of the same
# profile share one cache entry.
PREVIEW_WINDOW_STEP_MINUTES = 5
PREVIEW_TTL_SECONDS = 60


def _out(profile: Profile) -> ProfileOut:
    return ProfileOut(
        id=profile.id,
        version=profile.version,
        spec=ProfileSpec.model_validate(profile.spec),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


async def _get(session: SessionDep, profile_id: uuid.UUID) -> Profile:
    profile = await session.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Профиль не найден.")
    return profile


@router.get("/profiles")
async def list_profiles(session: SessionDep) -> list[ProfileOut]:
    rows = await session.execute(select(Profile).order_by(Profile.created_at))
    return [_out(profile) for profile in rows.scalars()]


@router.post("/profiles", status_code=status.HTTP_201_CREATED, dependencies=[_write_limit])
async def create_profile(spec: ProfileSpec, session: SessionDep) -> ProfileOut:
    profile = Profile(name=spec.name, spec=spec.model_dump(mode="json"))
    session.add(profile)
    await session.flush()
    await session.refresh(profile)
    return _out(profile)


@router.get("/profiles/{profile_id}")
async def get_profile(profile_id: uuid.UUID, session: SessionDep) -> ProfileOut:
    return _out(await _get(session, profile_id))


@router.put("/profiles/{profile_id}", dependencies=[_write_limit])
async def update_profile(
    profile_id: uuid.UUID, spec: ProfileSpec, session: SessionDep
) -> ProfileOut:
    """Replace the profile. The version grows only when the content changed."""
    profile = await _get(session, profile_id)
    new_spec = spec.model_dump(mode="json")
    if new_spec != profile.spec:
        profile.name = spec.name
        profile.spec = new_spec
        profile.version += 1
        await session.flush()
        await session.refresh(profile)
    return _out(profile)


@router.delete(
    "/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_write_limit]
)
async def delete_profile(profile_id: uuid.UUID, session: SessionDep) -> Response:
    await session.delete(await _get(session, profile_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/selection/preview", dependencies=[_preview_limit])
async def preview_selection(
    payload: PreviewRequest, session: SessionDep, cache: CacheDep, settings: SettingsDep
) -> PreviewOut:
    """Show what the profile would select right now, by retrieval evidence alone."""
    embedder = get_embedder()
    now = datetime.now(UTC)
    step = PREVIEW_WINDOW_STEP_MINUTES
    end = now.replace(minute=now.minute - now.minute % step, second=0, microsecond=0) + timedelta(
        minutes=step
    )
    start = end - timedelta(days=payload.period_days)
    key = (
        f"preview:{embedder.model_id}:{payload.profile.fingerprint()}:"
        f"{payload.profile.min_score}:{payload.profile.max_items}:{start.isoformat()}"
    )
    cached = await cache.get_json(key)
    if cached is not None:
        return PreviewOut.model_validate(cached)

    preview = await build_preview(
        session,
        profile=payload.profile,
        start=start,
        end=end,
        embedder=embedder,
        embed_queries=CachedQueryEmbedder(embedder, cache),
        per_interest_limit=settings.per_interest_limit,
        candidate_limit=settings.candidate_limit,
    )
    items = []
    for graded in preview.graded[:PREVIEW_ITEMS]:
        article = graded.article
        interest = payload.profile.interest(graded.interest_id)
        items.append(
            PreviewItem(
                article_id=article.id,
                url=article.url,
                title=article.title,
                source_name=article.source_name,
                published_at=article.published_at,
                score=round(graded.score, 3),
                interest_id=graded.interest_id,
                interest_title=interest.title if interest else None,
                lexical_hit=graded.candidate.lexical_hit,
                selected=article.id in preview.selected_ids,
                reject_reason=preview.rejected.get(article.id),
            )
        )
    out = PreviewOut(
        window_total=preview.window_total,
        candidates=len(preview.graded),
        selected=len(preview.selected_ids),
        lexical_only=preview.lexical_only,
        embedding_model=embedder.model_id,
        items=items,
    )
    await cache.set_json(key, out.model_dump(mode="json"), PREVIEW_TTL_SECONDS)
    return out
