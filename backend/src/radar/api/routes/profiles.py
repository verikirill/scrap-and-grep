"""Reader profiles and the instant selection preview."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select

from radar.ai.factory import get_embedder
from radar.api.deps import CacheDep, CurrentUser, SessionDep, SettingsDep, user_rate_limit
from radar.api.schemas import PreviewItem, PreviewOut, PreviewRequest, ProfileLook, ProfileOut
from radar.db.models import Profile
from radar.domain import ProfileSpec
from radar.logging import get_logger
from radar.pipeline.sql_store import CachedQueryEmbedder
from radar.recsys.service import forget_taste
from radar.selection.preview import build_preview
from radar.worker.tasks import refresh_taste

router = APIRouter(tags=["profiles"])
log = get_logger(__name__)

_write_limit = Depends(user_rate_limit("write", lambda settings: settings.rate_limit_per_minute))
_preview_limit = Depends(
    user_rate_limit("preview", lambda settings: settings.preview_rate_limit_per_minute)
)
# A reader needs a handful of profiles; the cap keeps one account from
# filling the table.
MAX_PROFILES_PER_USER = 30

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
        icon=profile.icon,
        color=profile.color,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


async def _get(session: SessionDep, user: CurrentUser, profile_id: uuid.UUID) -> Profile:
    """The reader's own profile. Someone else's is reported as missing, so the
    answer does not confirm that the id exists."""
    profile = (
        await session.execute(
            select(Profile).where(Profile.id == profile_id, Profile.user_id == user.id)
        )
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Профиль не найден.")
    return profile


async def _taste_changed(session: SessionDep, cache: CacheDep, user_id: uuid.UUID) -> None:
    """Interests are part of the taste. Commit first, then let caches go:
    the other way round, a request in between would cache the old version.
    """
    await session.commit()
    await forget_taste(cache, user_id)
    try:
        await refresh_taste.kiq(str(user_id))
    except Exception as exc:
        # Only the "readers alike" vector lags behind until the next signal.
        log.warning("taste_refresh_not_queued", error=type(exc).__name__)


@router.get("/profiles")
async def list_profiles(session: SessionDep, user: CurrentUser) -> list[ProfileOut]:
    rows = await session.execute(
        select(Profile).where(Profile.user_id == user.id).order_by(Profile.created_at, Profile.id)
    )
    return [_out(profile) for profile in rows.scalars()]


@router.post("/profiles", status_code=status.HTTP_201_CREATED, dependencies=[_write_limit])
async def create_profile(
    spec: ProfileSpec, session: SessionDep, user: CurrentUser, cache: CacheDep
) -> ProfileOut:
    owned = await session.scalar(
        select(func.count()).select_from(Profile).where(Profile.user_id == user.id)
    )
    if int(owned or 0) >= MAX_PROFILES_PER_USER:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Слишком много профилей, удалите лишние."
        )
    profile = Profile(user_id=user.id, name=spec.name, spec=spec.model_dump(mode="json"))
    session.add(profile)
    await session.flush()
    await session.refresh(profile)
    await _taste_changed(session, cache, user.id)
    return _out(profile)


@router.get("/profiles/{profile_id}")
async def get_profile(profile_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> ProfileOut:
    return _out(await _get(session, user, profile_id))


@router.put("/profiles/{profile_id}", dependencies=[_write_limit])
async def update_profile(
    profile_id: uuid.UUID,
    spec: ProfileSpec,
    session: SessionDep,
    user: CurrentUser,
    cache: CacheDep,
) -> ProfileOut:
    """Replace the profile. The version grows only when the content changed."""
    profile = await _get(session, user, profile_id)
    new_spec = spec.model_dump(mode="json")
    if new_spec != profile.spec:
        profile.name = spec.name
        profile.spec = new_spec
        profile.version += 1
        await session.flush()
        await session.refresh(profile)
        await _taste_changed(session, cache, user.id)
    return _out(profile)


@router.patch("/profiles/{profile_id}/look", dependencies=[_write_limit])
async def set_look(
    profile_id: uuid.UUID, look: ProfileLook, session: SessionDep, user: CurrentUser
) -> ProfileOut:
    """The icon and colour; the profile's content and version stay as they are."""
    profile = await _get(session, user, profile_id)
    profile.icon, profile.color = look.icon, look.color
    await session.commit()
    await session.refresh(profile)
    return _out(profile)


@router.delete(
    "/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_write_limit]
)
async def delete_profile(
    profile_id: uuid.UUID, session: SessionDep, user: CurrentUser, cache: CacheDep
) -> Response:
    await session.delete(await _get(session, user, profile_id))
    await _taste_changed(session, cache, user.id)
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
