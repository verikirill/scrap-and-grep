"""Connecting bots and channels: every claim is checked with Telegram first."""

import re
import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from radar.db.models import TelegramBot, TelegramChannel
from radar.publishing.secrets import TOKEN_RE, encrypt_token, token_hint
from radar.publishing.settings import ChannelSettings, Style
from radar.publishing.telegram import TelegramClient, TelegramError

_USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")
_LINK_RE = re.compile(r"^(?:https?://)?(?:www\.)?(?:t|telegram)\.me/(?:s/)?([A-Za-z0-9_]+)/?$")
POSTING_CHATS = frozenset({"channel", "supergroup", "group"})


class PublishingRefused(ValueError):
    """A request Telegram or the rules refuse, in words for the reader."""


def parse_chat(reference: str) -> int | str:
    """ "@name", "name", "https://t.me/name" or a numeric id like -1001234567890."""
    value = reference.strip()
    link = _LINK_RE.match(value)
    if link:
        value = link.group(1)
    if re.fullmatch(r"-?\d{5,20}", value):
        return int(value)
    value = value.removeprefix("@")
    if not _USERNAME_RE.match(value):
        raise PublishingRefused("Укажите @имя канала, ссылку t.me/имя или числовой id чата.")
    return f"@{value}"


async def add_bot(
    session: AsyncSession,
    user_id: uuid.UUID,
    token: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> TelegramBot:
    """Check the token with getMe and store it encrypted. The same bot added
    again only gets its token replaced."""
    token = token.strip()
    if not TOKEN_RE.match(token):
        raise PublishingRefused("Это не похоже на токен бота от @BotFather.")
    try:
        info = await TelegramClient(token, transport=transport).get_me()
    except TelegramError as exc:
        raise PublishingRefused(
            "Telegram не принял токен: проверьте, что он скопирован целиком."
        ) from exc
    existing = await session.scalar(
        select(TelegramBot).where(
            TelegramBot.user_id == user_id, TelegramBot.telegram_id == info.id
        )
    )
    bot = existing or TelegramBot(user_id=user_id, telegram_id=info.id)
    bot.username = info.username[:64]
    bot.name = info.name[:128] or info.username[:128]
    bot.token_encrypted = encrypt_token(token)
    bot.token_hint = token_hint(token)
    bot.status, bot.last_error, bot.checked_at = "ok", None, datetime.now(UTC)
    if existing is None:
        session.add(bot)
    await session.flush()
    return bot


async def add_channel(
    session: AsyncSession,
    user_id: uuid.UUID,
    bot: TelegramBot,
    client: TelegramClient,
    reference: str,
    *,
    profile_id: uuid.UUID | None,
) -> TelegramChannel:
    """Find the chat and make sure the bot may post there before saving it."""
    chat_ref = parse_chat(reference)
    try:
        chat = await client.get_chat(chat_ref)
        allowed = await client.can_post(chat.id, bot.telegram_id)
    except TelegramError as exc:
        raise PublishingRefused(
            "Бот не видит этот чат. Добавьте бота в канал администратором и повторите."
        ) from exc
    if chat.type not in POSTING_CHATS:
        raise PublishingRefused("Публиковать можно в канал или группу.")
    if not allowed:
        raise PublishingRefused(
            "У бота нет права публиковать сообщения: дайте его в настройках администратора."
        )
    existing = await session.scalar(
        select(TelegramChannel).where(
            TelegramChannel.user_id == user_id, TelegramChannel.chat_id == chat.id
        )
    )
    channel = existing or TelegramChannel(
        user_id=user_id,
        chat_id=chat.id,
        settings=ChannelSettings(style=Style(signature=chat.title[:64])).model_dump(mode="json"),
        profile_id=profile_id,
    )
    channel.bot_id = bot.id
    channel.title = chat.title[:256]
    channel.username = chat.username
    channel.status, channel.last_error = "ok", None
    if existing is None:
        session.add(channel)
    await session.flush()
    return channel
