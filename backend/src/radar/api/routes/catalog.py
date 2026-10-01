"""Sources and articles: the raw material a digest is built from."""

from datetime import datetime
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from radar.api.deps import (
    SessionDep,
    SettingsDep,
    admin_user,
    current_user,
    user_rate_limit,
)
from radar.api.schemas import ArticleOut, Page, SourceCreate, SourceOut, SourceUpdate
from radar.db.models import Article, Source
from radar.domain import Language, SourceCategory
from radar.ingest import telegram
from radar.ingest.net import UnsafeUrlError, build_client, ensure_public_url
from radar.ingest.pages import MarkupChanged
from radar.logging import get_logger
from radar.store.articles import ArticleFilter, list_articles
from radar.text import stable_hash
from radar.worker.tasks import ingest_all, ingest_source_task

# The catalogue is shared by every reader: anyone signed in may read it, only
# an administrator may change it.
router = APIRouter(tags=["catalog"], dependencies=[Depends(current_user)])
log = get_logger(__name__)

_write_limit = Depends(user_rate_limit("write", lambda settings: settings.rate_limit_per_minute))
_admin = Depends(admin_user)


def _article_out(article: Article) -> ArticleOut:
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
    )


async def _source_out(session: SessionDep, source: Source) -> SourceOut:
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
    return out.model_copy(update={"articles": counts.total, "articles_last_day": counts.day})


@router.get("/sources")
async def list_sources(session: SessionDep) -> list[SourceOut]:
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
                }
            )
        )
    return result


@router.post("/sources", status_code=status.HTTP_201_CREATED, dependencies=[_admin, _write_limit])
async def create_source(payload: SourceCreate, session: SessionDep) -> SourceOut:
    source = await (_channel(payload) if payload.kind == "telegram" else _feed(payload))
    session.add(source)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Источник уже добавлен.") from exc
    await session.commit()
    await ingest_source_task.kiq(source.id)
    return await _source_out(session, source)


async def _feed(payload: SourceCreate) -> Source:
    feed_url = str(payload.feed_url)
    try:
        await ensure_public_url(feed_url)
    except UnsafeUrlError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return Source(
        slug=f"custom-{stable_hash(feed_url)[:12]}",
        name=payload.name,
        feed_url=feed_url,
        site_url=str(payload.site_url) if payload.site_url else None,
        category=payload.category,
        language=payload.language,
        fetch_full_text=payload.fetch_full_text,
    )


async def _channel(payload: SourceCreate) -> Source:
    """A public channel, checked once before it is added: t.me must show its posts."""
    try:
        name = telegram.parse_channel(payload.channel or "")
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    try:
        async with build_client() as client:
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
    )


@router.patch("/sources/{source_id}", dependencies=[_admin, _write_limit])
async def update_source(source_id: int, payload: SourceUpdate, session: SessionDep) -> SourceOut:
    source = await session.get(Source, source_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Источник не найден.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, field, value)
    await session.flush()
    return await _source_out(session, source)


@router.delete(
    "/sources/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[_admin, _write_limit],
)
async def delete_source(source_id: int, session: SessionDep) -> Response:
    source = await session.get(Source, source_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Источник не найден.")
    await session.delete(source)
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
    dependencies=[_admin, _write_limit],
)
async def refresh_source(source_id: int, session: SessionDep) -> dict[str, str]:
    if await session.get(Source, source_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Источник не найден.")
    await ingest_source_task.kiq(source_id)
    return {"status": "queued"}


@router.get("/articles")
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
    articles, total = await list_articles(session, flt, limit, offset)
    return Page[ArticleOut](
        items=[_article_out(article) for article in articles],
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
