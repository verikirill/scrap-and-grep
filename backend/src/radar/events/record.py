"""Events built from what the API and the workers already have at hand.

Recording is a side line: every function here returns at once while events
are off, and none of them raises. A failure is logged and the request or the
task goes on as if nothing had been recorded. Queries run in a savepoint of
the caller's session, so a failed one cannot spoil the caller's commit.

Article events carry the source and its category, so the daily aggregates
need no join. Each reader has an hourly budget of events: a script cannot
fill the stream and push other readers' events out of it.
"""

import functools
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from redis.exceptions import RedisError
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from radar.auth.sessions import AuthUser
from radar.cache import get_redis
from radar.db import session_scope
from radar.db.models import Article, Digest, Profile, Source, User
from radar.events.emit import emit, enabled
from radar.events.model import (
    DIGEST_BUILT,
    DIGEST_OPENED,
    IMPRESSION,
    MCP_CALL,
    NIL,
    SERVED,
    SHARE_ACCEPTED,
    SLOT_DIGEST,
    SUGGESTION_ACCEPTED,
    SUGGESTION_DISMISSED,
    UNDO,
    Event,
)
from radar.logging import get_logger
from radar.ranker import features
from radar.ranker.serving import assignment

if TYPE_CHECKING:
    from radar.recsys.service import FeedPage

log = get_logger(__name__)

SURFACE_FEED = "feed"
SURFACE_DIGEST = "digest"
SURFACE_PROFILES = "profiles"
SURFACE_MCP = "mcp"
# A reader scrolling for an hour makes a few hundred events.
READER_EVENTS_PER_HOUR = 3_000
# A feed page asked for again (a refetch, another tab) is recorded once.
_SERVED_TTL = 1800


@dataclass(frozen=True, slots=True)
class Placement:
    """Where the reader met an article: the list, the place in it and why it was there."""

    article_id: int
    position: int = 0
    slot: str = ""


def _quiet[**P](record: Callable[P, Awaitable[None]]) -> Callable[P, Awaitable[None]]:
    @functools.wraps(record)
    async def guarded(*args: P.args, **kwargs: P.kwargs) -> None:
        if not enabled():
            return
        try:
            await record(*args, **kwargs)
        except Exception as exc:
            log.warning("event_not_recorded", what=record.__name__, error=type(exc).__name__)

    return guarded


async def _within_budget(user_id: uuid.UUID, count: int) -> bool:
    key = f"radar:events:budget:{user_id}:{datetime.now(UTC):%Y%m%d%H}"
    try:
        async with get_redis().pipeline(transaction=True) as pipe:
            pipe.incrby(key, count)
            pipe.expire(key, 3600, nx=True)
            used, _ = await pipe.execute()
    except RedisError:
        return True
    if int(used) > READER_EVENTS_PER_HOUR:
        log.warning("events_over_budget", user_id=str(user_id))
        return False
    return True


async def _first_time(key: str) -> bool:
    try:
        return bool(await get_redis().set(key, 1, nx=True, ex=_SERVED_TTL))
    except RedisError:
        return True


async def _articles(session: AsyncSession, ids: Sequence[int]) -> dict[int, tuple[int, str]]:
    """Article id -> (source id, source category) for the ids that exist."""
    rows = await session.execute(
        select(Article.id, Article.source_id, Source.category)
        .join(Source, Source.id == Article.source_id)
        .where(Article.id.in_(list(set(ids))))
    )
    return {article_id: (source_id, category) for article_id, source_id, category in rows.all()}


async def _adaptive(session: AsyncSession, user_id: uuid.UUID) -> bool:
    found = await session.scalar(
        select(exists().where(Profile.user_id == user_id, Profile.adaptive.is_(True)))
    )
    return bool(found)


@_quiet
async def served(session: AsyncSession, user: AuthUser, page: FeedPage) -> None:
    """A page of the feed as it was shown: places, scores and their parts."""
    if not page.items:
        return
    first = page.items[0].position
    # The order is in the key: the same list newest first is another page.
    served_key = f"radar:events:served:{page.snapshot}:{page.order}:{first}:{len(page.items)}"
    if not await _first_time(served_key):
        return
    if not await _within_budget(user.id, len(page.items)):
        return
    async with session.begin_nested():
        adaptive = await _adaptive(session, user.id)
    request_id = uuid.UUID(page.snapshot)
    ranking = page.ranking
    await emit(
        *(
            Event(
                SERVED,
                user.id,
                is_guest=user.is_demo,
                surface=SURFACE_FEED,
                article_id=item.article_id,
                source_id=item.source_id,
                category=item.source_category,
                request_id=request_id,
                position=item.position,
                slot=item.slot,
                adaptive=adaptive,
                score=item.score,
                features=features.served(item.parts, item.score, ranking.confidence),
                variant=ranking.variant,
                model_version=ranking.model_version,
            )
            for item in page.items
        )
    )


async def _placed(
    session: AsyncSession,
    user: AuthUser,
    event: str,
    surface: str,
    list_id: uuid.UUID | None,
    placements: Sequence[Placement],
) -> None:
    # One event per article: a list that names an article twice says nothing more.
    unique = list({placement.article_id: placement for placement in placements}.values())
    if not unique or not await _within_budget(user.id, len(unique)):
        return
    async with session.begin_nested():
        known = await _articles(session, [placement.article_id for placement in unique])
        adaptive = await _adaptive(session, user.id)
    arm = await assignment(user.id)
    await emit(
        *(
            Event(
                event,
                user.id,
                is_guest=user.is_demo,
                surface=surface,
                article_id=placement.article_id,
                source_id=known[placement.article_id][0],
                category=known[placement.article_id][1],
                request_id=list_id or NIL,
                position=placement.position,
                slot=placement.slot or (SLOT_DIGEST if surface == SURFACE_DIGEST else ""),
                adaptive=adaptive,
                variant=arm.variant,
            )
            for placement in unique
            if placement.article_id in known
        )
    )


@_quiet
async def seen(
    session: AsyncSession,
    user: AuthUser,
    surface: str,
    list_id: uuid.UUID | None,
    placements: Sequence[Placement],
) -> None:
    """Articles the reader saw on screen. Unknown article ids are skipped."""
    await _placed(session, user, IMPRESSION, surface, list_id, placements)


@_quiet
async def marked(
    session: AsyncSession,
    user: AuthUser,
    kind: str,
    *,
    active: bool,
    surface: str,
    list_id: uuid.UUID | None,
    placement: Placement,
) -> None:
    """A mark set or taken back: "like", or "like_undo"."""
    event = kind if active else f"{kind}{UNDO}"
    await _placed(session, user, event, surface, list_id, [placement])


@_quiet
async def digest_built(digest_id: uuid.UUID) -> None:
    """A digest finished: its origin (manual, schedule) and how many articles it took."""
    async with session_scope() as session:
        row = (
            await session.execute(
                select(Digest.user_id, Digest.profile_id, Digest.origin, Digest.stats, User.is_demo)
                .join(User, User.id == Digest.user_id)
                .where(Digest.id == digest_id)
            )
        ).first()
    if row is None:
        return
    user_id, profile_id, origin, stats, is_guest = row
    await emit(
        Event(
            DIGEST_BUILT,
            user_id,
            is_guest=is_guest,
            surface=SURFACE_DIGEST,
            request_id=digest_id,
            profile_id=profile_id or NIL,
            detail=origin,
            value=float((stats or {}).get("selected") or 0),
        )
    )


@_quiet
async def digest_opened(
    user: AuthUser, digest_id: uuid.UUID, profile_id: uuid.UUID | None, origin: str
) -> None:
    if not await _first_time(f"radar:events:digest-opened:{user.id}:{digest_id}"):
        return
    await emit(
        Event(
            DIGEST_OPENED,
            user.id,
            is_guest=user.is_demo,
            surface=SURFACE_DIGEST,
            request_id=digest_id,
            profile_id=profile_id or NIL,
            detail=origin,
        )
    )


@_quiet
async def suggestion_decided(
    user: AuthUser, profile_id: uuid.UUID, kind: str, *, accepted: bool
) -> None:
    await emit(
        Event(
            SUGGESTION_ACCEPTED if accepted else SUGGESTION_DISMISSED,
            user.id,
            is_guest=user.is_demo,
            surface=SURFACE_PROFILES,
            profile_id=profile_id,
            detail=kind,
        )
    )


@_quiet
async def share_accepted(user: AuthUser, profile_id: uuid.UUID) -> None:
    await emit(
        Event(
            SHARE_ACCEPTED,
            user.id,
            is_guest=user.is_demo,
            surface=SURFACE_PROFILES,
            profile_id=profile_id,
        )
    )


@_quiet
async def mcp_called(user_id: uuid.UUID, tool: str, items: int) -> None:
    """A call through MCP: the tool and how many items it answered with."""
    if not await _within_budget(user_id, 1):
        return
    async with session_scope() as session:
        is_guest = bool(await session.scalar(select(User.is_demo).where(User.id == user_id)))
    await emit(
        Event(
            MCP_CALL,
            user_id,
            is_guest=is_guest,
            surface=SURFACE_MCP,
            detail=tool,
            value=float(items),
        )
    )
