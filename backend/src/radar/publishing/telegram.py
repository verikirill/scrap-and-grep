"""A thin client for the Telegram Bot API: only the calls posting needs.

A library would bring its own event loop helpers, polling and handler
machinery; posting to channels needs eight HTTP calls and their errors. The
calls are plain JSON over httpx, like the other services this backend talks
to, and tests replace the transport.

The token is part of every URL. It never appears in an exception message or
a log line: errors carry the method name and Telegram's own description.
"""

import json
from dataclasses import dataclass
from typing import Any

import httpx

from radar.config import get_settings

# Telegram's own words for a chat the bot cannot reach any more.
GONE_PHRASES = (
    "chat not found",
    "bot was kicked",
    "not a member",
    "have no rights",
    "not enough rights",
)
# ... and for a picture or video it could not fetch or use.
MEDIA_PHRASES = (
    "wrong file",
    "failed to get http url content",
    "web page content",
    "photo_invalid",
    "image_process_failed",
    "wrong remote file",
)


class TelegramError(Exception):
    def __init__(
        self, method: str, code: int, description: str, retry_after: int | None = None
    ) -> None:
        super().__init__(f"{method}: {code} {description}")
        self.method = method
        self.code = code
        self.description = description
        self.retry_after = retry_after

    @property
    def is_rate_limited(self) -> bool:
        return self.code == httpx.codes.TOO_MANY_REQUESTS

    @property
    def is_temporary(self) -> bool:
        """Telegram's own failure: the request was not carried out, try again."""
        return self.code >= httpx.codes.INTERNAL_SERVER_ERROR

    @property
    def lost_access(self) -> bool:
        """The bot was removed from the chat or lost the right to post."""
        text = self.description.lower()
        return self.code in {401, 403} or any(phrase in text for phrase in GONE_PHRASES)

    @property
    def bad_media(self) -> bool:
        """Telegram could not fetch or use the picture or video at the given URL."""
        text = self.description.lower()
        return self.code == httpx.codes.BAD_REQUEST and any(
            phrase in text for phrase in MEDIA_PHRASES
        )


# Tests point every client at the mock Bot API in-process through this.
DEFAULT_TRANSPORT: httpx.AsyncBaseTransport | None = None


class TelegramUnavailable(Exception):
    """The Bot API did not answer.

    `may_have_arrived` is set when the request went out and the answer was
    lost: Telegram has no idempotency key, so such a post must not be sent
    again blindly.
    """

    def __init__(self, message: str, *, may_have_arrived: bool = False) -> None:
        super().__init__(message)
        self.may_have_arrived = may_have_arrived


# The request never left: the connection was not made.
_NOT_SENT = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)


@dataclass(frozen=True, slots=True)
class ChatInfo:
    id: int
    title: str
    username: str | None
    type: str


@dataclass(frozen=True, slots=True)
class BotInfo:
    id: int
    username: str
    name: str


class TelegramClient:
    def __init__(
        self,
        token: str,
        *,
        base_url: str | None = None,
        timeout: float | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self._token = token
        self._base = (base_url or settings.telegram_api_url).rstrip("/")
        self._timeout = httpx.Timeout(timeout or settings.telegram_timeout_seconds, connect=10.0)
        self._transport = transport or DEFAULT_TRANSPORT

    async def _post(self, method: str, **request: Any) -> Any:
        url = f"{self._base}/bot{self._token}/{method}"
        # The exception texts may contain the URL, and with it the token.
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.post(url, **request)
        except _NOT_SENT as exc:
            raise TelegramUnavailable(f"{method}: {type(exc).__name__}") from None
        except httpx.HTTPError as exc:
            raise TelegramUnavailable(
                f"{method}: {type(exc).__name__}", may_have_arrived=True
            ) from None
        return self._result(method, response)

    async def call(self, method: str, payload: dict[str, Any] | None = None) -> Any:
        return await self._post(method, json=payload or {})

    async def get_me(self) -> BotInfo:
        result = await self.call("getMe")
        return BotInfo(
            id=int(result["id"]),
            username=result.get("username") or "",
            name=result.get("first_name") or "",
        )

    async def get_chat(self, chat: int | str) -> ChatInfo:
        result = await self.call("getChat", {"chat_id": chat})
        return ChatInfo(
            id=int(result["id"]),
            title=result.get("title") or result.get("username") or str(result["id"]),
            username=result.get("username"),
            type=result.get("type") or "",
        )

    async def can_post(self, chat_id: int, bot_id: int) -> bool:
        """Whether the bot is an administrator allowed to post in the chat."""
        member = await self.call("getChatMember", {"chat_id": chat_id, "user_id": bot_id})
        status = member.get("status")
        if status == "creator":
            return True
        return status == "administrator" and member.get("can_post_messages", True) is not False

    async def send(self, method: str, payload: dict[str, Any]) -> Any:
        return await self.call(method, payload)

    async def send_file(
        self,
        method: str,
        payload: dict[str, Any],
        *,
        field: str,
        filename: str,
        data: bytes,
        content_type: str,
    ) -> Any:
        """The same call with the picture uploaded, for when Telegram cannot
        fetch it by its address. Nested values go as JSON strings, as the Bot
        API expects in multipart requests."""
        fields = {
            key: value if isinstance(value, str) else json.dumps(value)
            for key, value in payload.items()
            if key != field and value is not None
        }
        return await self._post(method, data=fields, files={field: (filename, data, content_type)})

    def _result(self, method: str, response: httpx.Response) -> Any:
        status = response.status_code
        try:
            body = response.json()
        except ValueError:
            body = None
        if not isinstance(body, dict):
            # A proxy's error page: a gateway error means Telegram never had
            # the request; anything else, nobody knows.
            raise TelegramUnavailable(
                f"{method}: unexpected answer {status}",
                may_have_arrived=status < httpx.codes.INTERNAL_SERVER_ERROR,
            )
        if body.get("ok"):
            return body.get("result")
        parameters = body.get("parameters") or {}
        raise TelegramError(
            method=method,
            code=int(body.get("error_code") or status),
            description=str(body.get("description") or "")[:300],
            retry_after=parameters.get("retry_after"),
        )


def message_link(username: str | None, chat_id: int, message_id: int) -> str:
    """The t.me address of a post: by name in a public channel, by id in a private one."""
    if username:
        return f"https://t.me/{username}/{message_id}"
    internal = str(chat_id).removeprefix("-100")
    return f"https://t.me/c/{internal}/{message_id}"
