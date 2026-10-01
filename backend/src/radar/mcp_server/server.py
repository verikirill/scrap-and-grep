"""The reader's news as an MCP server, for AI assistants.

Every tool answers for one reader only: the one whose key came with the
request. The key is checked before a request reaches MCP, and no tool takes
a reader or a user id as an argument, so an assistant cannot ask for anyone
else's news.

The server is stateless and answers in JSON: any replica of the api can take
any call, and nothing has to stick a client to one of them.
"""

import uuid
from datetime import datetime

from mcp.server import MCPServer
from mcp.server.auth.middleware.auth_context import AuthContextMiddleware, get_access_token
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.auth.provider import AccessToken
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, Field
from sqlalchemy import select
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from radar.api.reading import measure_soon
from radar.cache import get_cache
from radar.config import get_settings
from radar.db import session_scope
from radar.db.models import Profile
from radar.domain import ProfileSpec
from radar.mcp_server import keys
from radar.recsys import service as feed_service
from radar.recsys.service import FeedItem
from radar.render.markdown import render_markdown
from radar.store import digests as digest_store
from radar.text import content_tokens
from radar.views import digest_summary, digest_view

SCOPE = "news:read"
TOO_MANY = "Слишком много запросов, повторите через минуту."
MAX_ITEMS = 50
# A query word matches a word of the article that starts with its stem: the
# word without its last two letters, the usual length of a Russian ending,
# but never shorter than this. "шлюзы" finds "шлюзах", "уязвимость" finds
# "уязвимостей".
MIN_STEM = 4

mcp = MCPServer(
    "Tail&Grep",
    instructions=(
        "Новости ИТ и информационной безопасности, подобранные под этого читателя: "
        "его персональная лента, сохранённые статьи, его дайджесты и интересы. "
        "Отвечай по этим данным и давай ссылки на источники."
    ),
)


class News(BaseModel):
    id: int
    title: str
    summary: str
    url: str
    source: str
    published_at: datetime
    reading_minutes: int | None = Field(
        default=None, description="Время чтения полной статьи; нет, если текст ещё не прочитан."
    )
    why: list[str] = Field(default_factory=list, description="Почему статья в ленте читателя.")


class NewsList(BaseModel):
    items: list[News]
    total: int


class DigestBrief(BaseModel):
    id: str
    title: str | None
    profile: str
    period_start: datetime
    period_end: datetime
    status: str
    articles: int


class DigestList(BaseModel):
    digests: list[DigestBrief]


class InterestBrief(BaseModel):
    title: str
    keywords: list[str]


class ProfileBrief(BaseModel):
    name: str
    role: str
    interests: list[InterestBrief]
    exclusions: list[str]


class Interests(BaseModel):
    profiles: list[ProfileBrief]


def _reader() -> uuid.UUID:
    """The owner of the key the request came with."""
    token = get_access_token()
    if token is None:
        raise PermissionError("Нужен ключ доступа Tail&Grep.")
    return uuid.UUID(token.client_id)


def _news(item: FeedItem) -> News:
    return News(
        id=item.article_id,
        title=item.title,
        summary=item.summary,
        url=item.url,
        source=item.source_name,
        published_at=item.published_at,
        reading_minutes=item.reading_minutes,
        why=[reason.text for reason in item.reasons],
    )


async def _feed(reader: uuid.UUID, limit: int, offset: int = 0) -> tuple[list[FeedItem], int]:
    settings = get_settings()
    async with session_scope() as session:
        items, total, _ = await feed_service.feed_page(
            session,
            get_cache(),
            reader,
            window_days=settings.feed_window_days,
            ttl=settings.feed_cache_seconds,
            limit=limit,
            offset=offset,
        )
    # Times not known yet are found for the next call, as for the web feed.
    await measure_soon(item.article_id for item in items if item.reading_minutes is None)
    return items, total


def _stem(token: str) -> str:
    return token[: max(MIN_STEM, len(token) - 2)]


def matches(query: str, item: FeedItem) -> bool:
    """Every word of the query is in the title or the summary, by its stem."""
    stems = {_stem(token) for token in content_tokens(query)}
    words = content_tokens(f"{item.title} {item.summary}")
    return bool(stems) and all(any(word.startswith(stem) for word in words) for stem in stems)


@mcp.tool()
async def my_feed(
    limit: int = Field(default=10, ge=1, le=MAX_ITEMS), offset: int = Field(default=0, ge=0)
) -> NewsList:
    """Персональная лента читателя за последние две недели, лучшее сверху, с причинами."""
    items, total = await _feed(_reader(), limit, offset)
    return NewsList(items=[_news(item) for item in items], total=total)


@mcp.tool()
async def search_my_news(
    query: str = Field(min_length=2, max_length=200),
    limit: int = Field(default=10, ge=1, le=MAX_ITEMS),
) -> NewsList:
    """Поиск по ленте читателя: только среди новостей, подобранных под него."""
    items, _ = await _feed(_reader(), feed_service.FEED_SIZE)
    found = [item for item in items if matches(query, item)]
    return NewsList(items=[_news(item) for item in found[:limit]], total=len(found))


@mcp.tool()
async def saved_news(limit: int = Field(default=10, ge=1, le=MAX_ITEMS)) -> NewsList:
    """Статьи, которые читатель сохранил."""
    async with session_scope() as session:
        items, total = await feed_service.saved_page(session, _reader(), limit=limit, offset=0)
    return NewsList(items=[_news(item) for item in items], total=total)


@mcp.tool()
async def my_digests(limit: int = Field(default=10, ge=1, le=MAX_ITEMS)) -> DigestList:
    """Дайджесты читателя, новые сверху."""
    async with session_scope() as session:
        digests = await digest_store.list_recent(session, _reader(), None, limit)
    summaries = [digest_summary(digest) for digest in digests]
    return DigestList(
        digests=[
            DigestBrief(
                id=str(summary.id),
                title=summary.title,
                profile=summary.profile_name,
                period_start=summary.period_start,
                period_end=summary.period_end,
                status=summary.status,
                articles=int(summary.stats.get("selected") or 0),
            )
            for summary in summaries
        ]
    )


@mcp.tool()
async def read_digest(digest_id: str = Field(description="id из my_digests")) -> str:
    """Готовый дайджест читателя в Markdown: темы, выжимки, ссылки на источники."""
    try:
        wanted = uuid.UUID(digest_id)
    except ValueError:
        raise ValueError("Такого дайджеста нет.") from None
    async with session_scope() as session:
        digest = await digest_store.get(session, wanted, user_id=_reader(), full=True)
        if digest is None or digest.status != digest_store.STATUS_DONE:
            raise ValueError("Такого готового дайджеста нет.")
        return render_markdown(digest_view(digest))


@mcp.tool()
async def my_interests() -> Interests:
    """Профили интересов читателя: роль, темы с ключевыми словами, что не показывать."""
    async with session_scope() as session:
        rows = await session.scalars(
            select(Profile)
            .where(Profile.user_id == _reader())
            .order_by(Profile.created_at, Profile.id)
        )
        specs = [ProfileSpec.model_validate(row.spec) for row in rows]
    return Interests(
        profiles=[
            ProfileBrief(
                name=spec.name,
                role=spec.role,
                interests=[
                    InterestBrief(title=interest.title, keywords=list(interest.keywords))
                    for interest in spec.interests
                ],
                exclusions=list(spec.exclusions),
            )
            for spec in specs
        ]
    )


class KeyAuth:
    """Lets a request through to MCP only with a valid reader's key."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = AuthContextMiddleware(app)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        header = dict(scope["headers"]).get(b"authorization", b"").decode("latin-1")
        token = header[7:].strip() if header[:7].lower() == "bearer " else ""
        reader = None
        if token:
            async with session_scope() as session:
                reader = await keys.owner(session, token)
        if reader is None:
            response = JSONResponse(
                {"error": "invalid_token", "detail": "Нужен действующий ключ доступа Tail&Grep."},
                status_code=401,
                headers={"WWW-Authenticate": 'Bearer realm="tail-and-grep"'},
            )
            await response(scope, receive, send)
            return
        # Counted per reader, so a key that loops does not slow anyone else.
        limit = get_settings().mcp_rate_limit_per_minute
        if await get_cache().hit_rate_limit(f"mcp:u:{reader}", limit):
            response = JSONResponse(
                {"error": "rate_limited", "detail": TOO_MANY},
                status_code=429,
                headers={"Retry-After": "60"},
            )
            await response(scope, receive, send)
            return
        scope["user"] = AuthenticatedUser(
            AccessToken(token=token, client_id=str(reader), scopes=[SCOPE])
        )
        await self.app(scope, receive, send)


def build() -> tuple[ASGIApp, StreamableHTTPSessionManager]:
    """The MCP endpoint behind key checks, and the session manager the api's
    lifespan has to run."""
    app = mcp.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        # The keys are what protects this endpoint; it is reached through the
        # gateway under whatever host name the stack is served.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    return KeyAuth(app), mcp.session_manager
