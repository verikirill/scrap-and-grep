"""The personal feed and the signals it learns from."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel

from radar.api.deps import CacheDep, CurrentUser, SessionDep, SettingsDep, user_rate_limit
from radar.api.reading import measure_soon
from radar.logging import get_logger
from radar.recsys import service, store
from radar.recsys.service import FeedItem, TasteOut
from radar.recsys.signals import Kind
from radar.worker.tasks import refresh_taste

router = APIRouter(tags=["feed"])
log = get_logger(__name__)

_feed_limit = Depends(user_rate_limit("feed", lambda settings: settings.feed_rate_limit_per_minute))
_write_limit = Depends(user_rate_limit("write", lambda settings: settings.rate_limit_per_minute))


class FeedOut(BaseModel):
    items: list[FeedItem]
    total: int
    limit: int
    offset: int
    generated_at: datetime
    # Pass it back for the next page to page the same ranking.
    snapshot: str | None = None


class FeedbackIn(BaseModel):
    article_id: int
    kind: Kind
    # False takes the signal back: an unlike, an unsave.
    active: bool = True
    context: Literal["feed", "digest"] = "feed"


@router.get("/feed", dependencies=[_feed_limit])
async def get_feed(
    user: CurrentUser,
    session: SessionDep,
    cache: CacheDep,
    settings: SettingsDep,
    limit: Annotated[int, Query(ge=1, le=60)] = 30,
    offset: Annotated[int, Query(ge=0, le=service.FEED_SIZE)] = 0,
    snapshot: Annotated[str | None, Query(pattern=r"^[0-9a-f]{32}$")] = None,
) -> FeedOut:
    """Articles of the last days ranked for the reader, with the reasons."""
    items, total, snapshot = await service.feed_page(
        session,
        cache,
        user.id,
        window_days=settings.feed_window_days,
        ttl=settings.feed_cache_seconds,
        limit=limit,
        offset=offset,
        snapshot=snapshot,
    )
    await measure_soon(item.article_id for item in items if item.reading_minutes is None)
    return FeedOut(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        generated_at=datetime.now(UTC),
        snapshot=snapshot,
    )


@router.get("/feed/saved")
async def get_saved(
    user: CurrentUser,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=60)] = 30,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> FeedOut:
    items, total = await service.saved_page(session, user.id, limit=limit, offset=offset)
    return FeedOut(
        items=items, total=total, limit=limit, offset=offset, generated_at=datetime.now(UTC)
    )


@router.post("/feedback", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_write_limit])
async def send_feedback(
    payload: FeedbackIn, user: CurrentUser, session: SessionDep, cache: CacheDep
) -> Response:
    """Record a like, a dislike, a save, a hide or an opened link."""
    known = await store.record(
        session,
        user.id,
        payload.article_id,
        payload.kind,
        active=payload.active,
        context=payload.context,
    )
    if not known:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Публикация не найдена.")
    await session.commit()
    # The next feed and the next digest are built from the new signal.
    await service.forget_taste(cache, user.id)
    try:
        await refresh_taste.kiq(str(user.id))
    except Exception as exc:
        # Only the "readers alike" vector lags behind; the signal itself is saved.
        log.warning("taste_refresh_not_queued", error=type(exc).__name__)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/reactions")
async def get_reactions(
    user: CurrentUser,
    session: SessionDep,
    article_id: Annotated[list[int], Query(min_length=1, max_length=200)],
) -> dict[int, list[str]]:
    """The reader's signals for the given articles, e.g. the items of a digest."""
    return await store.reactions(session, user.id, article_id)


@router.get("/taste")
async def get_taste(user: CurrentUser, session: SessionDep, cache: CacheDep) -> TasteOut:
    """What the recommender believes about the reader, in readable form."""
    return await service.taste_summary(session, cache, user.id)
