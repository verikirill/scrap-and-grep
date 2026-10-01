"""Events built from what the API and the workers already have at hand.

Every function here returns at once while events are off, before touching
the database. Article events carry the source and its category, so the
daily aggregates can be cut by them without a join.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from radar.auth.sessions import AuthUser
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
from radar.ranker import features
from radar.ranker.serving import assignment

if TYPE_CHECKING:
    from radar.recsys.service import FeedPage

SURFACE_FEED = "feed"
SURFACE_DIGEST = "digest"
SURFACE_PROFILES = "profiles"
SURFACE_MCP = "mcp"


@dataclass(frozen=True, slots=True)
class Placement:
    """Where the reader met an article: the list, the place in it and why it was there."""

    article_id: int
    position: int = 0
    slot: str = ""


async def _articles(session: AsyncSession, ids: Sequence[int]) -> dict[int, tuple[int, str]]:
    """Article id -> (source id, source category) for the ids that exist."""
    if not ids:
        return {}
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


async def served(session: AsyncSession, user: AuthUser, page: FeedPage) -> None:
    """A page of the feed as it was shown: places, scores and their parts."""
    if not enabled() or not page.items:
        return
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


async def seen(
    session: AsyncSession,
    user: AuthUser,
    surface: str,
    list_id: uuid.UUID | None,
    placements: Sequence[Placement],
    *,
    event: str = IMPRESSION,
) -> None:
    """Articles the reader saw or acted on. Unknown article ids are skipped."""
    if not enabled() or not placements:
        return
    known = await _articles(session, [placement.article_id for placement in placements])
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
            for placement in placements
            if placement.article_id in known
        )
    )


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
    await seen(
        session, user, surface, list_id, [placement], event=kind if active else f"{kind}{UNDO}"
    )


async def digest_built(digest_id: uuid.UUID) -> None:
    """A digest finished: its origin (manual, schedule) and how many articles it took."""
    if not enabled():
        return
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


async def digest_opened(
    user: AuthUser, digest_id: uuid.UUID, profile_id: uuid.UUID | None, origin: str
) -> None:
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


async def mcp_called(user_id: uuid.UUID, tool: str, items: int) -> None:
    """A call through MCP: the tool and how many items it answered with."""
    if not enabled():
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
