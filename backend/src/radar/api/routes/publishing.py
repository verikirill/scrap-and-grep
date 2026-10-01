"""Telegram publishing: bots, channels, their settings and their posts."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from radar.api.deps import CurrentUser, SessionDep, SettingsDep, user_rate_limit
from radar.db.models import Article, Profile, TelegramBot, TelegramChannel, TelegramPost
from radar.logging import get_logger
from radar.publishing import service as publishing_service
from radar.publishing.compose import channel_settings
from radar.publishing.content import PostContent
from radar.publishing.manage import PublishingRefused, add_bot, add_channel
from radar.publishing.schedule import next_slot
from radar.publishing.secrets import MIN_SECRET_CHARS, SecretKeyMissing, TokenUnreadable
from radar.publishing.settings import ChannelSettings
from radar.publishing.telegram import TelegramUnavailable
from radar.worker.tasks import compose_post, send_post

router = APIRouter(prefix="/publishing", tags=["publishing"])
log = get_logger(__name__)

_limit = Depends(
    user_rate_limit("publish", lambda settings: settings.publish_rate_limit_per_minute)
)
EDITABLE = (publishing_service.DRAFT, publishing_service.QUEUED, publishing_service.FAILED)
TELEGRAM_HOST = "api.telegram.org"
DISABLED_MESSAGE = "Публикация выключена: задайте RADAR_SECRET_KEY, чтобы хранить токены ботов."


class BotIn(BaseModel):
    token: str = Field(min_length=20, max_length=100)


class BotOut(BaseModel):
    id: uuid.UUID
    username: str
    name: str
    token_hint: str
    status: str
    last_error: str | None
    created_at: datetime
    channels: int


class ChannelIn(BaseModel):
    bot_id: uuid.UUID
    chat: str = Field(min_length=2, max_length=200)
    profile_id: uuid.UUID | None = None


class ChannelPatch(BaseModel):
    bot_id: uuid.UUID | None = None
    enabled: bool | None = None
    profile_id: uuid.UUID | None = None
    clear_profile: bool = False
    settings: ChannelSettings | None = None


class ChannelOut(BaseModel):
    id: uuid.UUID
    bot_id: uuid.UUID
    bot_username: str
    chat_id: int
    username: str | None
    title: str
    enabled: bool
    profile_id: uuid.UUID | None
    settings: ChannelSettings
    status: str
    last_error: str | None
    next_slot: datetime | None
    created_at: datetime
    counts: dict[str, int]


class ArticleBrief(BaseModel):
    id: int
    title: str
    url: str
    source: str
    image_url: str | None


class PostOut(BaseModel):
    id: uuid.UUID
    channel_id: uuid.UUID
    kind: str
    status: str
    slot_at: datetime | None
    not_before: datetime | None
    content: PostContent | None
    problems: list[str]
    by_model: bool
    message_url: str | None
    error: str | None
    created_at: datetime
    sent_at: datetime | None
    articles: list[ArticleBrief]


class PostCreate(BaseModel):
    kind: Literal["news", "digest"] = "news"
    article_id: int | None = None
    # Queue it as soon as it is written, or keep it as a draft to edit first.
    publish: bool = False


class PostPatch(BaseModel):
    content: PostContent | None = None
    # When to send; null sends at the next planner round once approved.
    not_before: datetime | None = None
    approve: bool = False


def _refused(exc: Exception) -> HTTPException:
    if isinstance(exc, SecretKeyMissing):
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=DISABLED_MESSAGE)
    if isinstance(exc, TokenUnreadable):
        return HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Токен бота сохранён под другим RADAR_SECRET_KEY: добавьте бота заново.",
        )
    if isinstance(exc, TelegramUnavailable):
        return HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail="Telegram не ответил. Повторите через минуту."
        )
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


async def _bot(session: SessionDep, user: CurrentUser, bot_id: uuid.UUID) -> TelegramBot:
    bot = await session.get(TelegramBot, bot_id)
    if bot is None or bot.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Бот не найден.")
    return bot


async def _channel(
    session: SessionDep, user: CurrentUser, channel_id: uuid.UUID
) -> TelegramChannel:
    channel = await session.get(TelegramChannel, channel_id)
    if channel is None or channel.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Канал не найден.")
    return channel


async def _post(
    session: SessionDep, user: CurrentUser, post_id: uuid.UUID, *, lock: bool = False
) -> TelegramPost:
    """The reader's post. `lock` holds the row until the request ends, so the
    planner cannot send it between the check of its status and the change."""
    post = await session.get(TelegramPost, post_id, with_for_update=lock)
    if post is None or post.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Пост не найден.")
    return post


async def _own_profile(session: SessionDep, user: CurrentUser, profile_id: uuid.UUID) -> None:
    profile = await session.get(Profile, profile_id)
    if profile is None or profile.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Профиль не найден.")


def _bot_out(bot: TelegramBot, channels: int) -> BotOut:
    return BotOut(
        id=bot.id,
        username=bot.username,
        name=bot.name,
        token_hint=bot.token_hint,
        status=bot.status,
        last_error=bot.last_error,
        created_at=bot.created_at,
        channels=channels,
    )


async def _channel_out(session: SessionDep, channel: TelegramChannel) -> ChannelOut:
    settings = channel_settings(channel)
    rows = await session.execute(
        select(TelegramPost.status, func.count())
        .where(TelegramPost.channel_id == channel.id)
        .group_by(TelegramPost.status)
    )
    upcoming = (
        next_slot(datetime.now(UTC), settings.schedule, str(channel.id))
        if channel.enabled and channel.profile_id
        else None
    )
    return ChannelOut(
        id=channel.id,
        bot_id=channel.bot_id,
        bot_username=channel.bot.username,
        chat_id=channel.chat_id,
        username=channel.username,
        title=channel.title,
        enabled=channel.enabled,
        profile_id=channel.profile_id,
        settings=settings,
        status=channel.status,
        last_error=channel.last_error,
        next_slot=upcoming,
        created_at=channel.created_at,
        counts={str(state): int(count) for state, count in rows.all()},
    )


async def _posts_out(session: SessionDep, posts: list[TelegramPost]) -> list[PostOut]:
    ids = {article_id for post in posts for article_id in post.article_ids}
    articles: dict[int, ArticleBrief] = {}
    if ids:
        rows = await session.scalars(select(Article).where(Article.id.in_(ids)))
        articles = {
            article.id: ArticleBrief(
                id=article.id,
                title=article.title,
                url=article.url,
                source=article.source.name,
                image_url=article.image_url,
            )
            for article in rows
        }
    out = []
    for post in posts:
        content = PostContent.model_validate(post.content) if post.content else None
        out.append(
            PostOut(
                id=post.id,
                channel_id=post.channel_id,
                kind=post.kind,
                status=post.status,
                slot_at=post.slot_at,
                not_before=post.not_before,
                content=content,
                problems=content.problems() if content else [],
                by_model=post.by_model,
                message_url=post.message_url,
                error=post.error,
                created_at=post.created_at,
                sent_at=post.sent_at,
                articles=[articles[i] for i in post.article_ids if i in articles],
            )
        )
    return out


@router.get("/defaults")
async def defaults(settings: SettingsDep, user: CurrentUser) -> dict[str, Any]:
    """Settings a new channel starts with, whether bots can be stored, and
    whether posts go to the real Telegram."""
    secret = settings.secret_key.get_secret_value() if settings.secret_key else ""
    return {
        "settings": ChannelSettings().model_dump(mode="json"),
        "enabled": len(secret) >= MIN_SECRET_CHARS,
        "mock": urlsplit(settings.telegram_api_url).hostname != TELEGRAM_HOST,
    }


def _approve(post: TelegramPost) -> None:
    """A human said yes: the post goes out however late it is, and gets a
    fresh set of attempts."""
    post.status, post.error = publishing_service.QUEUED, None
    post.publish_when_ready, post.attempts = False, 0


@router.get("/bots")
async def list_bots(session: SessionDep, user: CurrentUser) -> list[BotOut]:
    bots = (
        await session.scalars(
            select(TelegramBot)
            .where(TelegramBot.user_id == user.id)
            .order_by(TelegramBot.created_at)
        )
    ).all()
    counts = dict(
        (
            await session.execute(
                select(TelegramChannel.bot_id, func.count())
                .where(TelegramChannel.user_id == user.id)
                .group_by(TelegramChannel.bot_id)
            )
        ).all()
    )
    return [_bot_out(bot, counts.get(bot.id, 0)) for bot in bots]


@router.post("/bots", status_code=status.HTTP_201_CREATED, dependencies=[_limit])
async def create_bot(
    payload: BotIn, session: SessionDep, settings: SettingsDep, user: CurrentUser
) -> BotOut:
    count = await session.scalar(select(func.count()).where(TelegramBot.user_id == user.id))
    if (count or 0) >= settings.max_bots_per_user:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Ботов уже слишком много.")
    try:
        bot = await add_bot(session, user.id, payload.token)
    except (PublishingRefused, SecretKeyMissing, TelegramUnavailable) as exc:
        raise _refused(exc) from exc
    log.info("bot_added", bot=bot.username)
    return _bot_out(bot, 0)


@router.delete("/bots/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bot(bot_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> None:
    """Forget the bot and, with it, its channels and their posts."""
    await session.delete(await _bot(session, user, bot_id))


@router.get("/channels")
async def list_channels(session: SessionDep, user: CurrentUser) -> list[ChannelOut]:
    channels = (
        await session.scalars(
            select(TelegramChannel)
            .where(TelegramChannel.user_id == user.id)
            .order_by(TelegramChannel.created_at)
        )
    ).all()
    return [await _channel_out(session, channel) for channel in channels]


@router.post("/channels", status_code=status.HTTP_201_CREATED, dependencies=[_limit])
async def create_channel(
    payload: ChannelIn, session: SessionDep, settings: SettingsDep, user: CurrentUser
) -> ChannelOut:
    count = await session.scalar(select(func.count()).where(TelegramChannel.user_id == user.id))
    if (count or 0) >= settings.max_channels_per_user:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Каналов уже слишком много.")
    bot = await _bot(session, user, payload.bot_id)
    if payload.profile_id is not None:
        await _own_profile(session, user, payload.profile_id)
    try:
        client = publishing_service.bot_client(bot)
        channel = await add_channel(
            session, user.id, bot, client, payload.chat, profile_id=payload.profile_id
        )
    except (PublishingRefused, SecretKeyMissing, TokenUnreadable, TelegramUnavailable) as exc:
        raise _refused(exc) from exc
    await session.refresh(channel, ["bot"])
    return await _channel_out(session, channel)


@router.patch("/channels/{channel_id}", dependencies=[_limit])
async def update_channel(
    channel_id: uuid.UUID, payload: ChannelPatch, session: SessionDep, user: CurrentUser
) -> ChannelOut:
    channel = await _channel(session, user, channel_id)
    if payload.bot_id is not None:
        channel.bot_id = (await _bot(session, user, payload.bot_id)).id
    if payload.enabled is not None:
        channel.enabled = payload.enabled
        if payload.enabled:
            # Turning a channel on again is the owner's way to say "fixed".
            channel.status, channel.last_error = "ok", None
    if payload.clear_profile:
        channel.profile_id = None
    elif payload.profile_id is not None:
        await _own_profile(session, user, payload.profile_id)
        channel.profile_id = payload.profile_id
    if payload.settings is not None:
        channel.settings = payload.settings.model_dump(mode="json")
    await session.flush()
    await session.refresh(channel, ["bot"])
    return await _channel_out(session, channel)


@router.delete("/channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_channel(channel_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> None:
    await session.delete(await _channel(session, user, channel_id))


@router.get("/posts")
async def list_posts(
    session: SessionDep,
    user: CurrentUser,
    channel_id: uuid.UUID | None = None,
    state: Annotated[str | None, Query(alias="status", max_length=16)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[PostOut]:
    statement = select(TelegramPost).where(TelegramPost.user_id == user.id)
    if channel_id is not None:
        statement = statement.where(TelegramPost.channel_id == channel_id)
    if state:
        statement = statement.where(TelegramPost.status == state)
    posts = (
        await session.scalars(
            statement.order_by(
                func.coalesce(
                    TelegramPost.sent_at, TelegramPost.slot_at, TelegramPost.created_at
                ).desc()
            ).limit(limit)
        )
    ).all()
    return await _posts_out(session, list(posts))


@router.post(
    "/channels/{channel_id}/posts", status_code=status.HTTP_202_ACCEPTED, dependencies=[_limit]
)
async def create_post(
    channel_id: uuid.UUID, payload: PostCreate, session: SessionDep, user: CurrentUser
) -> PostOut:
    """Write a post now, outside the schedule: about a chosen article, or the
    best fresh one for the channel's audience."""
    channel = await _channel(session, user, channel_id)
    if payload.article_id is not None and await session.get(Article, payload.article_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Статья не найдена.")
    post = TelegramPost(
        id=uuid.uuid7(),
        channel_id=channel.id,
        user_id=user.id,
        kind=payload.kind,
        status=publishing_service.COMPOSING,
        article_ids=[payload.article_id] if payload.article_id is not None else [],
        publish_when_ready=payload.publish and channel_settings(channel).approval == "auto",
    )
    session.add(post)
    await session.commit()
    await compose_post.kiq(str(post.id))
    return (await _posts_out(session, [post]))[0]


@router.patch("/posts/{post_id}", dependencies=[_limit])
async def update_post(
    post_id: uuid.UUID, payload: PostPatch, session: SessionDep, user: CurrentUser
) -> PostOut:
    post = await _post(session, user, post_id, lock=True)
    if post.status not in EDITABLE:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Этот пост уже нельзя изменить.")
    if payload.content is not None:
        if payload.content.problems():
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail=" ".join(payload.content.problems())
            )
        post.content = payload.content.model_dump(mode="json")
    if "not_before" in payload.model_fields_set:
        post.not_before = payload.not_before
    if payload.approve:
        if post.content is None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Пост ещё не написан.")
        _approve(post)
    await session.flush()
    return (await _posts_out(session, [post]))[0]


@router.post("/posts/{post_id}/publish", dependencies=[_limit])
async def publish_post(post_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> PostOut:
    """Send now, whatever the schedule says."""
    post = await _post(session, user, post_id, lock=True)
    if post.status not in EDITABLE or post.content is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Этот пост сейчас нельзя отправить.")
    _approve(post)
    post.status, post.not_before = publishing_service.SENDING, None
    await session.commit()
    await send_post.kiq(str(post.id))
    return (await _posts_out(session, [post]))[0]


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(post_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> None:
    """Drop a post that is not out yet; a sent one stays in the history."""
    post = await _post(session, user, post_id, lock=True)
    if post.status in {publishing_service.SENT, publishing_service.SENDING}:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Отправленный пост не удаляется.")
    # A slot post is kept as skipped, so the planner does not plan it again.
    if post.slot_at is not None:
        post.status, post.content, post.error = publishing_service.SKIPPED, None, "Отменён вручную."
    else:
        await session.delete(post)
