"""The life of a post: planned for a slot, written, approved, sent.

The planner runs every minute. For every enabled channel it creates a post
row for each slot that is due within the preparation time (a unique index
on channel, kind and slot makes this idempotent) and queues the writing.
Written posts become drafts when a human approves them, otherwise they are
queued; queued posts whose time has come are handed to the sender.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from radar.cache import Cache
from radar.db import session_scope
from radar.db.models import Article, TelegramBot, TelegramChannel, TelegramPost
from radar.domain import ProfileSpec
from radar.images.service import mirror
from radar.images.store import get_image_store
from radar.ingest.net import build_client
from radar.logging import get_logger
from radar.publishing.compose import (
    Composed,
    NothingToPost,
    audience_profile,
    channel_settings,
    compose_digest,
    compose_news,
    pick_articles,
    told_elsewhere,
    told_here,
)
from radar.publishing.content import PostContent, requests_for, without_media
from radar.publishing.schedule import digest_slot, slots_to_prepare
from radar.publishing.secrets import decrypt_token
from radar.publishing.settings import ChannelSettings
from radar.publishing.telegram import (
    TelegramClient,
    TelegramError,
    TelegramUnavailable,
    message_link,
)

log = get_logger(__name__)

COMPOSING, DRAFT, QUEUED, SENDING, SENT, FAILED, SKIPPED = (
    "composing",
    "draft",
    "queued",
    "sending",
    "sent",
    "failed",
    "skipped",
)
# A post stuck in a transient state this long is taken over again.
STUCK_AFTER = timedelta(minutes=15)
MAX_ATTEMPTS = 5
RETRY_STEP = timedelta(minutes=2)
# Telegram allows a bot 20 messages a minute in one chat; a wait longer than
# this is not slept through inside a task, the post is just queued later.
MAX_INLINE_WAIT_SECONDS = 5


def utcnow() -> datetime:
    return datetime.now(UTC)


def bot_client(
    bot: TelegramBot, transport: httpx.AsyncBaseTransport | None = None
) -> TelegramClient:
    return TelegramClient(decrypt_token(bot.token_encrypted), transport=transport)


async def plan(now: datetime | None = None) -> list[uuid.UUID]:
    """Create the posts whose slots are due and return the ids to write."""
    now = now or utcnow()
    created: list[uuid.UUID] = []
    async with session_scope() as session:
        channels = (
            await session.scalars(
                select(TelegramChannel).where(
                    TelegramChannel.enabled.is_(True), TelegramChannel.status == "ok"
                )
            )
        ).all()
        for channel in channels:
            settings = channel_settings(channel)
            wanted: list[tuple[str, datetime]] = []
            if channel.profile_id is not None:
                wanted += [
                    ("news", slot)
                    for slot in slots_to_prepare(now, settings.schedule, str(channel.id))
                ]
            digest = digest_slot(now, settings.digest, settings.schedule)
            if digest is not None and channel.profile_id is not None:
                wanted.append(("digest", digest))
            for kind, slot in wanted:
                statement = (
                    insert(TelegramPost)
                    .values(
                        id=uuid.uuid7(),
                        channel_id=channel.id,
                        user_id=channel.user_id,
                        kind=kind,
                        status=COMPOSING,
                        slot_at=slot,
                        publish_when_ready=settings.approval == "auto",
                    )
                    .on_conflict_do_nothing(
                        index_elements=["channel_id", "kind", "slot_at"],
                        index_where=TelegramPost.slot_at.is_not(None),
                    )
                    .returning(TelegramPost.id)
                )
                post_id = (await session.execute(statement)).scalar_one_or_none()
                if post_id is not None:
                    created.append(post_id)
    return created


async def due(now: datetime | None = None) -> list[uuid.UUID]:
    """Queued posts whose time has come, marked as sending in one statement so
    that two planners cannot hand the same post out twice."""
    now = now or utcnow()
    async with session_scope() as session:
        result = await session.execute(
            update(TelegramPost)
            .where(
                TelegramPost.status == QUEUED,
                or_(TelegramPost.slot_at.is_(None), TelegramPost.slot_at <= now),
                or_(TelegramPost.not_before.is_(None), TelegramPost.not_before <= now),
            )
            .values(status=SENDING, updated_at=now)
            .returning(TelegramPost.id)
        )
        return [row[0] for row in result.all()]


async def recover(now: datetime | None = None) -> dict[str, list[uuid.UUID]]:
    """Posts whose worker died: written again or sent again."""
    now = now or utcnow()
    async with session_scope() as session:
        rewrite = await session.execute(
            update(TelegramPost)
            .where(TelegramPost.status == COMPOSING, TelegramPost.updated_at < now - STUCK_AFTER)
            .values(updated_at=now)
            .returning(TelegramPost.id)
        )
        resend = await session.execute(
            update(TelegramPost)
            .where(TelegramPost.status == SENDING, TelegramPost.updated_at < now - STUCK_AFTER)
            .values(status=QUEUED, updated_at=now)
            .returning(TelegramPost.id)
        )
        return {
            "compose": [row[0] for row in rewrite.all()],
            "requeued": [row[0] for row in resend.all()],
        }


async def compose(post_id: uuid.UUID, cache: Cache, *, now: datetime | None = None) -> str:
    """Write a planned post. Returns the status it ends in."""
    now = now or utcnow()
    async with session_scope() as session:
        post = await session.get(TelegramPost, post_id)
        if post is None or post.status != COMPOSING:
            return "gone"
        channel = await session.get(TelegramChannel, post.channel_id)
        if channel is None:
            return "gone"
        settings = channel_settings(channel)
        spec = await audience_profile(session, channel)
        try:
            async with build_client() as client:
                composed = await _write(session, post, channel, settings, spec, cache, client, now)
        except NothingToPost as exc:
            post.status, post.error = SKIPPED, str(exc)
            log.info("post_skipped", channel_id=str(channel.id), reason=str(exc))
            return SKIPPED
        post.content = composed.content.model_dump(mode="json")
        post.article_ids = composed.article_ids
        post.by_model = composed.by_model
        post.error = None
        post.status = QUEUED if post.publish_when_ready else DRAFT
        log.info("post_composed", post_id=str(post.id), status=post.status, kind=post.kind)
        return post.status


async def _write(
    session: AsyncSession,
    post: TelegramPost,
    channel: TelegramChannel,
    settings: ChannelSettings,
    spec: ProfileSpec | None,
    cache: Cache,
    client: httpx.AsyncClient,
    now: datetime,
) -> Composed:
    chosen = list(post.article_ids or [])
    if chosen:
        articles = list(
            (await session.scalars(select(Article).where(Article.id.in_(chosen)))).all()
        )
        articles.sort(key=lambda article: chosen.index(article.id))
    else:
        if spec is None:
            raise NothingToPost("у канала не выбрана аудитория")
        exclude = await told_here(session, channel.id)
        if settings.selection.network == "spread":
            since = now - timedelta(hours=settings.selection.network_hours)
            exclude |= await told_elsewhere(session, channel, since)
        if post.kind == "digest":
            start, count = now - timedelta(days=settings.digest.days), settings.digest.items
            exclude = set()
        else:
            start, count = now - timedelta(hours=settings.selection.freshness_hours), 1
        articles = await pick_articles(
            session,
            channel=channel,
            spec=spec,
            cache=cache,
            start=start,
            end=now,
            count=count,
            exclude=exclude,
            min_score=settings.selection.min_score,
        )
    if not articles:
        raise NothingToPost("нет свежих новостей под интересы аудитории, которых не было в канале")
    if post.kind == "digest":
        return await compose_digest(session, channel, articles, settings, spec, client)
    return await compose_news(session, channel, articles[0], settings, spec, client)


async def _deliver(
    client: TelegramClient, content: PostContent, chat_id: int, article: Article | None
) -> dict[str, Any]:
    """Send the post; when Telegram cannot fetch the picture, upload a stored
    copy, and failing that send the post without it."""
    calls = requests_for(content, chat_id)
    try:
        results = [await client.send(method, payload) for method, payload in calls]
    except TelegramError as exc:
        if not exc.bad_media or not content.media:
            raise
        method, payload = calls[0]
        copy = None
        if article is not None and method in {"sendPhoto", "sendVideo"}:
            async with build_client() as http:
                copy = await mirror(article, http, get_image_store())
        if copy is not None:
            field = "video" if method == "sendVideo" else "photo"
            result = await client.send_file(
                method,
                payload,
                field=field,
                filename=f"picture.{copy.extension}",
                data=copy.data,
                content_type=copy.content_type,
            )
            return result if isinstance(result, dict) else {}
        log.info("post_picture_dropped", reason=exc.description[:120])
        fallback = without_media(content)
        if article is not None and fallback.preview_url is None:
            fallback = fallback.model_copy(update={"preview_url": article.url})
        results = [await client.send(m, p) for m, p in requests_for(fallback, chat_id)]
    first = results[0]
    if isinstance(first, list):
        first = first[0] if first else {}
    return first if isinstance(first, dict) else {}


async def send(
    post_id: uuid.UUID,
    *,
    now: datetime | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> str:
    """Publish a post marked as sending. Returns the status it ends in."""
    now = now or utcnow()
    async with session_scope() as session:
        post = await session.get(TelegramPost, post_id)
        if post is None or post.status != SENDING or post.content is None:
            return "gone"
        channel = await session.get(TelegramChannel, post.channel_id)
        if channel is None:
            return "gone"
        content = PostContent.model_validate(post.content)
        article = await session.get(Article, post.article_ids[0]) if post.article_ids else None
        post.attempts += 1
        try:
            message = await _deliver(
                bot_client(channel.bot, transport), content, channel.chat_id, article
            )
        except TelegramError as exc:
            return _failed_send(post, channel, exc, now)
        except TelegramUnavailable as exc:
            return _retry_later(post, str(exc), now)
        message_id = message.get("message_id")
        post.status, post.sent_at, post.error = SENT, now, None
        if isinstance(message_id, int):
            post.message_id = message_id
            post.message_url = message_link(channel.username, channel.chat_id, message_id)
        if channel.last_error:
            channel.last_error = None
        log.info("post_sent", post_id=str(post.id), channel_id=str(channel.id))
        return SENT


def _retry_later(post: TelegramPost, error: str, now: datetime) -> str:
    if post.attempts >= MAX_ATTEMPTS:
        post.status, post.error = FAILED, f"Telegram не ответил: {error}"[:500]
        return FAILED
    post.status, post.error = QUEUED, error[:500]
    post.not_before = now + RETRY_STEP * post.attempts
    return QUEUED


def _failed_send(
    post: TelegramPost, channel: TelegramChannel, exc: TelegramError, now: datetime
) -> str:
    if exc.is_rate_limited:
        post.status = QUEUED
        post.not_before = now + timedelta(seconds=(exc.retry_after or 30) + 1)
        post.error = "Telegram попросил подождать"
        return QUEUED
    post.status, post.error = FAILED, f"Telegram: {exc.description}"[:500]
    if exc.lost_access:
        # Nothing will reach this chat until the owner fixes the bot's rights.
        channel.status = "error"
        channel.last_error = f"Бот не может писать в канал: {exc.description}"[:500]
    log.warning("post_failed", post_id=str(post.id), code=exc.code, error=exc.description[:200])
    return FAILED
