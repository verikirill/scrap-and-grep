"""Article persistence: inserts, listing, embeddings."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from radar.db.models import Article, ArticleEmbedding, Source
from radar.domain import ArticleRef

EMBED_TEXT_LIMIT = 1500


@dataclass(frozen=True, slots=True)
class NewArticle:
    url: str
    title: str
    summary: str
    content: str | None
    author: str | None
    tags: tuple[str, ...]
    language: str
    published_at: datetime
    content_hash: str


@dataclass(frozen=True, slots=True)
class ArticleFilter:
    query: str | None = None
    source_ids: tuple[int, ...] = ()
    categories: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    since: datetime | None = None
    until: datetime | None = None


def embedding_text(title: str, summary: str, content: str | None) -> str:
    body = summary if len(summary) >= 200 or not content else content
    return f"{title}\n{body[:EMBED_TEXT_LIMIT]}"


def to_ref(article: Article) -> ArticleRef:
    return ArticleRef(
        id=article.id,
        url=article.url,
        title=article.title,
        summary=article.summary,
        content=article.content,
        source_name=article.source.name,
        source_category=article.source.category,
        language=article.language,
        published_at=article.published_at,
        content_hash=article.content_hash,
    )


async def insert_new(
    session: AsyncSession, source_id: int, articles: Sequence[NewArticle]
) -> list[int]:
    """Insert articles that are not stored yet and return their ids.

    The unique URL constraint makes the call idempotent, so a task that is
    redelivered after a worker crash cannot create duplicates.
    """
    if not articles:
        return []
    rows = [
        {
            "source_id": source_id,
            "url": item.url,
            "title": item.title,
            "summary": item.summary,
            "content": item.content,
            "author": item.author,
            "tags": list(item.tags),
            "language": item.language,
            "published_at": item.published_at,
            "content_hash": item.content_hash,
        }
        for item in articles
    ]
    statement = (
        insert(Article)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["url"])
        .returning(Article.id)
    )
    result = await session.execute(statement)
    return [row[0] for row in result.all()]


async def known_urls(session: AsyncSession, urls: Sequence[str]) -> set[str]:
    if not urls:
        return set()
    result = await session.execute(select(Article.url).where(Article.url.in_(urls)))
    return {row[0] for row in result.all()}


def _apply_filter(statement: Any, flt: ArticleFilter) -> Any:
    if flt.source_ids:
        statement = statement.where(Article.source_id.in_(flt.source_ids))
    if flt.categories:
        statement = statement.where(Source.category.in_(flt.categories))
    if flt.languages:
        statement = statement.where(Article.language.in_(flt.languages))
    if flt.since:
        statement = statement.where(Article.published_at >= flt.since)
    if flt.until:
        statement = statement.where(Article.published_at < flt.until)
    if flt.query:
        tsquery = func.websearch_to_tsquery("russian", flt.query)
        statement = statement.where(Article.search_tsv.op("@@")(tsquery))
    return statement


async def list_articles(
    session: AsyncSession, flt: ArticleFilter, limit: int, offset: int
) -> tuple[list[Article], int]:
    base = _apply_filter(select(Article).join(Source, Article.source_id == Source.id), flt)
    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    if flt.query:
        rank = func.ts_rank_cd(Article.search_tsv, func.websearch_to_tsquery("russian", flt.query))
        ordered = base.order_by(rank.desc(), Article.published_at.desc())
    else:
        ordered = base.order_by(Article.published_at.desc(), Article.id.desc())
    result = await session.execute(ordered.limit(limit).offset(offset))
    return list(result.scalars().all()), int(total or 0)


async def get_refs(session: AsyncSession, ids: Sequence[int]) -> dict[int, ArticleRef]:
    if not ids:
        return {}
    result = await session.execute(select(Article).where(Article.id.in_(ids)))
    return {article.id: to_ref(article) for article in result.scalars().all()}


async def pending_embeddings(
    session: AsyncSession,
    model: str,
    limit: int,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[tuple[int, str]]:
    """Articles that have no vector for `model` yet, newest first."""
    missing = ~(
        select(ArticleEmbedding.article_id)
        .where(ArticleEmbedding.article_id == Article.id, ArticleEmbedding.model == model)
        .exists()
    )
    statement = select(Article.id, Article.title, Article.summary, Article.content).where(missing)
    if since:
        statement = statement.where(Article.published_at >= since)
    if until:
        statement = statement.where(Article.published_at < until)
    result = await session.execute(statement.order_by(Article.published_at.desc()).limit(limit))
    return [(row.id, embedding_text(row.title, row.summary, row.content)) for row in result.all()]


async def save_embeddings(
    session: AsyncSession, model: str, vectors: Sequence[tuple[int, list[float]]]
) -> None:
    if not vectors:
        return
    rows = [
        {"article_id": article_id, "model": model, "embedding": vector}
        for article_id, vector in vectors
    ]
    await session.execute(insert(ArticleEmbedding).values(rows).on_conflict_do_nothing())


async def load_vectors(
    session: AsyncSession, model: str, ids: Sequence[int]
) -> dict[int, np.ndarray]:
    if not ids:
        return {}
    result = await session.execute(
        select(ArticleEmbedding.article_id, ArticleEmbedding.embedding).where(
            ArticleEmbedding.model == model, ArticleEmbedding.article_id.in_(ids)
        )
    )
    return {row[0]: np.asarray(row[1], dtype=np.float32) for row in result.all()}


async def corpus_stats(session: AsyncSession, model: str) -> dict[str, Any]:
    row = (
        await session.execute(
            text(
                """
                SELECT count(*) AS articles,
                       count(*) FILTER (
                           WHERE published_at >= now() - interval '24 hours'
                       ) AS last_day,
                       min(published_at) AS oldest,
                       max(published_at) AS newest,
                       (SELECT count(*) FROM article_embeddings WHERE model = :model) AS embedded
                FROM articles
                """
            ),
            {"model": model},
        )
    ).one()
    return dict(row._mapping)
