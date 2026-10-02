"""The personal feed and the signals it learns from."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from radar.api.adapting import adapt_soon
from radar.api.deps import CacheDep, CurrentUser, SessionDep, SettingsDep, user_rate_limit
from radar.api.reading import measure_soon
from radar.events import record
from radar.events.record import Placement
from radar.logging import get_logger
from radar.recsys import service, store
from radar.recsys.service import FeedItem, TasteOut
from radar.recsys.signals import Kind
from radar.worker.tasks import refresh_taste

router = APIRouter(tags=["feed"])
log = get_logger(__name__)

_feed_limit = Depends(user_rate_limit("feed", lambda settings: settings.feed_rate_limit_per_minute))
_write_limit = Depends(user_rate_limit("write", lambda settings: settings.rate_limit_per_minute))


class FreshOut(BaseModel):
    # Articles that arrived after the reader's feed was ranked and pass their interests.
    fresh: int


class FeedOut(BaseModel):
    items: list[FeedItem]
    total: int
    limit: int
    offset: int
    generated_at: datetime
    # When the list behind the page was ranked: /feed/fresh counts arrivals since.
    built_at: datetime | None = None
    # Pass it back for the next page to page the same ranking.
    snapshot: str | None = None


# Why an article was in the list the reader acted on.
Slot = Literal["", "ranked", "explore", "newest", "saved", "digest"]
# A bigint article id: anything outside it is no article, and is a 422.
ArticleId = Annotated[int, Field(ge=1, le=2**63 - 1)]
MAX_POSITION = 1000


class FeedbackIn(BaseModel):
    article_id: ArticleId
    kind: Kind
    # False takes the signal back: an unlike, an unsave.
    active: bool = True
    context: Literal["feed", "digest"] = "feed"
    # Where the article was: the feed snapshot or the digest, the place in
    # it and why it was there. Only for the events; the mark is the same.
    list_id: uuid.UUID | None = None
    position: int = Field(default=0, ge=0, le=MAX_POSITION)
    slot: Slot = ""


@router.get("/feed", dependencies=[_feed_limit])
async def get_feed(
    user: CurrentUser,
    session: SessionDep,
    cache: CacheDep,
    settings: SettingsDep,
    limit: Annotated[int, Query(ge=1, le=60)] = 30,
    offset: Annotated[int, Query(ge=0, le=service.FEED_SIZE)] = 0,
    snapshot: Annotated[str | None, Query(pattern=r"^[0-9a-f]{32}$")] = None,
    order: Literal["top", "new"] = "top",
) -> FeedOut:
    """Articles of the last days for the reader, with the reasons: ranked
    ("top"), or the relevant ones newest first ("new")."""
    page = await service.feed_page(
        session,
        cache,
        user.id,
        window_days=settings.feed_window_days,
        ttl=settings.feed_cache_seconds,
        limit=limit,
        offset=offset,
        snapshot=snapshot,
        order=order,
    )
    # Pages of the shown articles are read for a length or a picture they lack.
    await measure_soon(
        item.article_id
        for item in page.items
        if item.reading_minutes is None or not item.has_picture
    )
    await record.served(session, user, page)
    return FeedOut(
        items=page.items,
        total=page.total,
        limit=limit,
        offset=offset,
        generated_at=datetime.now(UTC),
        snapshot=page.snapshot,
        built_at=page.built_at,
    )


@router.get("/feed/fresh", dependencies=[_feed_limit])
async def get_fresh(
    user: CurrentUser,
    session: SessionDep,
    cache: CacheDep,
    settings: SettingsDep,
    since: datetime,
) -> FreshOut:
    """Whether the feed on the reader's screen has fallen behind: an open page
    asks now and then, and offers the new articles when there are any."""
    fresh = await service.fresh_since(
        session,
        cache,
        user.id,
        window_days=settings.feed_window_days,
        ttl=settings.feed_cache_seconds,
        since=since,
    )
    return FreshOut(fresh=fresh)


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
    # Adaptive profiles learn from the same mark.
    await adapt_soon(user.id)
    await record.marked(
        session,
        user,
        payload.kind,
        active=payload.active,
        surface=payload.context,
        list_id=payload.list_id,
        placement=Placement(payload.article_id, payload.position, payload.slot),
    )
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
