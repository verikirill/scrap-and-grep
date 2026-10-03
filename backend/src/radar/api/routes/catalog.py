"""Sources and articles: the raw material a digest is built from."""

import asyncio
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from radar.ai.factory import get_embedder
from radar.api.deps import (
    CacheDep,
    CatalogWriter,
    CurrentUser,
    SessionDep,
    SettingsDep,
    admin_user,
    current_user,
    is_admin,
    user_rate_limit,
)
from radar.api.schemas import (
    ArticleOut,
    DetectIn,
    DetectOut,
    Page,
    SourceCreate,
    SourceOut,
    SourceUpdate,
)
from radar.auth.sessions import AuthUser
from radar.config import Settings
from radar.db.models import Article, Source
from radar.domain import Language, SourceCategory
from radar.images.store import get_image_store
from radar.ingest import telegram, wordpress
from radar.ingest.avatars import avatar_key
from radar.ingest.detect import detect_key
from radar.ingest.net import UnsafeUrlError, build_client, ensure_public_url
from radar.ingest.pages import MarkupChanged
from radar.logging import get_logger
from radar.store.articles import ArticleFilter, Meaning, find_articles
from radar.text import stable_hash
from radar.worker.tasks import detect_source_task, ingest_all, ingest_source_task

# The catalogue is shared by every reader: anyone signed in may read it. An
# administrator changes it; in an open catalogue (RADAR_OPEN_CATALOG) every
# reader may add a source and change or remove the ones they added.
router = APIRouter(tags=["catalog"], dependencies=[Depends(current_user)])
log = get_logger(__name__)

_write_limit = Depends(user_rate_limit("write", lambda settings: settings.rate_limit_per_minute))
# A search embeds the query and compares it with every article in the filters.
_search_limit = Depends(user_rate_limit("search", lambda settings: settings.rate_limit_per_minute))
# A query longer to embed than this is searched by its words alone.
MEANING_TIMEOUT_SECONDS = 10
# A detection's id: a uuid4 in hex.
DETECT_ID_LENGTH = 32
_admin = Depends(admin_user)


def _article_out(article: Article, match: Literal["words", "meaning"] | None = None) -> ArticleOut:
    return ArticleOut(
        id=article.id,
        url=article.url,
        title=article.title,
        summary=article.summary,
        has_full_text=bool(article.content),
        source_id=article.source_id,
        source_name=article.source.name,
        source_category=article.source.category,
        language=article.language,
        tags=article.tags,
        published_at=article.published_at,
        match=match,
    )


async def _meaning(query: str | None) -> Meaning | None:
    """The query as a vector, when the embedder understands meaning at all.

    The search still answers by words when the embedding server is down.
    """
    embedder = get_embedder()
    if not query or not embedder.semantic:
        return None
    try:
        async with asyncio.timeout(MEANING_TIMEOUT_SECONDS):
            [vector] = await embedder.embed([query], "query")
    except Exception as exc:
        log.warning("search_meaning_unavailable", error=type(exc).__name__)
        return None
    return Meaning(vector=vector, model=embedder.model_id, floor=embedder.search_floor)


def _may_edit(source: Source, user: AuthUser, settings: Settings) -> bool:
    if is_admin(user):
        return True
    return settings.open_catalog and source.added_by is not None and source.added_by == user.id


async def _editable(
    session: SessionDep, user: AuthUser, settings: Settings, source_id: int
) -> Source:
    source = await session.get(Source, source_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Источник не найден.")
    if not _may_edit(source, user, settings):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Этот источник меняет администратор или тот, кто его добавил.",
        )
    return source


async def _source_out(session: SessionDep, source: Source, *, can_edit: bool = False) -> SourceOut:
    counts = (
        await session.execute(
            text(
                """
                SELECT count(*) AS total,
                       count(*) FILTER (WHERE published_at >= now() - interval '24 hours') AS day
                FROM articles WHERE source_id = :source_id
                """
            ),
            {"source_id": source.id},
        )
    ).one()
    out = SourceOut.model_validate(source)
    return out.model_copy(
        update={"articles": counts.total, "articles_last_day": counts.day, "can_edit": can_edit}
    )


@router.get("/sources/avatars")
async def source_avatars(session: SessionDep) -> dict[int, str]:
    """Sources that have a picture, each with a version for the picture's address."""
    rows = await session.execute(
        select(Source.id, Source.avatar_updated_at).where(Source.avatar_updated_at.is_not(None))
    )
    return {source_id: f"{updated:%Y%m%d%H%M%S}" for source_id, updated in rows.all() if updated}


@router.get("/sources/{source_id}/avatar")
async def source_avatar(source_id: int) -> Response:
    data = await get_image_store().get(avatar_key(source_id))
    if data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No picture for this source")
    # The address carries the picture's version, so it may be kept long.
    return Response(
        content=data,
        media_type="image/webp",
        headers={
            "Cache-Control": "private, max-age=2592000, immutable",
            "Content-Security-Policy": "default-src 'none'",
        },
    )


@router.get("/sources")
async def list_sources(
    session: SessionDep, user: CurrentUser, settings: SettingsDep
) -> list[SourceOut]:
    counts = {
        row.source_id: row
        for row in (
            await session.execute(
                text(
                    """
                    SELECT source_id,
                           count(*) AS total,
                           count(*) FILTER (
                               WHERE published_at >= now() - interval '24 hours'
                           ) AS day
                    FROM articles GROUP BY source_id
                    """
                )
            )
        ).all()
    }
    sources = (
        await session.execute(select(Source).order_by(Source.category, Source.name))
    ).scalars()
    result = []
    for source in sources:
        row = counts.get(source.id)
        result.append(
            SourceOut.model_validate(source).model_copy(
                update={
                    "articles": row.total if row else 0,
                    "articles_last_day": row.day if row else 0,
                    "can_edit": _may_edit(source, user, settings),
                }
            )
        )
    return result


@router.post("/sources", status_code=status.HTTP_201_CREATED, dependencies=[_write_limit])
async def create_source(
    payload: SourceCreate, session: SessionDep, user: CatalogWriter
) -> SourceOut:
    source = await (_channel(payload) if payload.kind == "telegram" else _feed(payload))
    source.added_by = user.id
    session.add(source)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Источник уже добавлен.") from exc
    await session.commit()
    await ingest_source_task.kiq(source.id)
    return await _source_out(session, source, can_edit=True)


@router.post("/sources/detect", status_code=status.HTTP_202_ACCEPTED, dependencies=[_write_limit])
async def start_detect(payload: DetectIn, _: CatalogWriter) -> dict[str, str]:
    """Find out what an address is and how to read it. That is the ingest
    worker's job, where the browser is; the answer is asked for by its id."""
    request_id = uuid.uuid4().hex
    await detect_source_task.kiq(request_id, payload.address, payload.link_selector)
    return {"request_id": request_id}


@router.get("/sources/detect/{request_id}")
async def detect_result(request_id: str, cache: CacheDep, _: CatalogWriter) -> DetectOut:
    if not request_id.isalnum() or len(request_id) != DETECT_ID_LENGTH:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Проверка не найдена.")
    answer = await cache.get_json(detect_key(request_id))
    if answer is None:
        return DetectOut(status="pending")
    if not answer.get("ok"):
        return DetectOut(status="done", error=str(answer.get("error") or "Адрес не прочитан."))
    return DetectOut.model_validate({"status": "done", "found": answer["found"]})


async def _feed(payload: SourceCreate) -> Source:
    """A feed, a news page or a WordPress API: each is polled at its address."""
    feed_url = str(payload.feed_url)
    if payload.kind == "wordpress" and not wordpress.is_posts_url(feed_url):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Для WordPress нужен адрес API записей: /wp-json/wp/v2/posts.",
        )
    try:
        await ensure_public_url(feed_url)
    except UnsafeUrlError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return Source(
        slug=f"custom-{stable_hash(feed_url)[:12]}",
        name=payload.name,
        kind=payload.kind,
        link_selector=payload.link_selector,
        feed_url=feed_url,
        site_url=str(payload.site_url) if payload.site_url else None,
        category=payload.category,
        language=payload.language,
        fetch_full_text=payload.fetch_full_text,
        proxy_url=payload.proxy_url,
    )


async def _channel(payload: SourceCreate) -> Source:
    """A public channel, checked once before it is added: t.me must show its posts."""
    try:
        name = telegram.parse_channel(payload.channel or "")
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    try:
        async with build_client(proxy=payload.proxy_url) as client:
            title = await telegram.channel_title(client, name)
    except telegram.ChannelUnavailable as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Канал @{name} не найден или закрыл веб-превью: так его читать нельзя.",
        ) from exc
    except MarkupChanged as exc:
        log.warning("channel_page_unreadable", channel=name, error=str(exc))
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail="t.me ответил страницей, в которой не нашлось постов канала.",
        ) from exc
    except (httpx.HTTPError, OSError, UnsafeUrlError) as exc:
        log.warning("channel_check_failed", channel=name, error=type(exc).__name__)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=(
                "t.me не ответил. Если Telegram недоступен из сети сервера, "
                "задайте зеркало в RADAR_TELEGRAM_PREVIEW_URLS."
            ),
        ) from exc
    return Source(
        slug=f"tg-{name}",
        name=payload.name or (title if len(title) >= 2 else f"@{name}")[:200],
        kind="telegram",
        feed_url=telegram.feed_url(name),
        site_url=telegram.site_url(name),
        category=payload.category,
        language=payload.language,
        fetch_full_text=payload.fetch_full_text,
        proxy_url=payload.proxy_url,
    )


@router.patch("/sources/{source_id}", dependencies=[_write_limit])
async def update_source(
    source_id: int,
    payload: SourceUpdate,
    session: SessionDep,
    user: CurrentUser,
    settings: SettingsDep,
) -> SourceOut:
    source = await _editable(session, user, settings, source_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, field, value)
    await session.flush()
    return await _source_out(session, source, can_edit=True)


@router.delete(
    "/sources/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[_write_limit],
)
async def delete_source(
    source_id: int, session: SessionDep, user: CurrentUser, settings: SettingsDep
) -> Response:
    await session.delete(await _editable(session, user, settings, source_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/sources/refresh", status_code=status.HTTP_202_ACCEPTED, dependencies=[_admin, _write_limit]
)
async def refresh_sources() -> dict[str, str]:
    """Queue a fetch of every enabled source."""
    await ingest_all.kiq()
    return {"status": "queued"}


@router.post(
    "/sources/{source_id}/refresh",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[_write_limit],
)
async def refresh_source(
    source_id: int, session: SessionDep, user: CurrentUser, settings: SettingsDep
) -> dict[str, str]:
    await _editable(session, user, settings, source_id)
    await ingest_source_task.kiq(source_id)
    return {"status": "queued"}


@router.get("/articles", dependencies=[_search_limit])
async def search_articles(
    session: SessionDep,
    settings: SettingsDep,
    q: Annotated[str | None, Query(max_length=200)] = None,
    source_id: Annotated[list[int] | None, Query(max_length=50)] = None,
    category: Annotated[list[SourceCategory] | None, Query(max_length=5)] = None,
    language: Annotated[list[Language] | None, Query(max_length=2)] = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> Page[ArticleOut]:
    flt = ArticleFilter(
        query=q.strip() if q and q.strip() else None,
        source_ids=tuple(source_id or ()),
        categories=tuple(category or ()),
        languages=tuple(language or ()),
        since=since,
        until=until,
    )
    # No connection waits on the embedding server.
    await session.commit()
    meaning = await _meaning(flt.query)
    found, total = await find_articles(session, flt, limit, offset, meaning)
    words: Literal["words"] | None = "words" if flt.query else None
    return Page[ArticleOut](
        items=[
            _article_out(article, "meaning" if by_meaning else words)
            for article, by_meaning in found
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/articles/timeline")
async def article_timeline(
    session: SessionDep, days: Annotated[int, Query(ge=1, le=90)] = 14
) -> list[dict[str, Any]]:
    """Articles per day and category, for the activity chart."""
    day = func.date_trunc("day", Article.published_at).label("day")
    rows = await session.execute(
        select(day, Source.category, func.count().label("count"))
        .join(Source, Source.id == Article.source_id)
        .where(Article.published_at >= func.now() - func.make_interval(0, 0, 0, days))
        .group_by(day, Source.category)
        .order_by(day)
    )
    return [{"day": row.day, "category": row.category, "count": row.count} for row in rows.all()]
