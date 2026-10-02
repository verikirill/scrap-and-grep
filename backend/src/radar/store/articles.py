"""Article persistence: inserts, listing, embeddings."""

import re
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
    image_url: str | None = None
    word_count: int | None = None


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
            "image_url": item.image_url,
            "word_count": item.word_count,
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


# Matches by meaning follow the matches by words, at most this many.
MEANING_LIMIT = 30
# An article found only by meaning must stand out among those searched (z-score)
# and be close in absolute terms (the embedder's search floor). With fewer
# articles than this in the filters there is no telling what stands out.
MEANING_MIN_Z = 3.0
MEANING_MIN_SCOPE = 50
# Identifiers are looked up as written: by meaning, CVE-2026-88772 is near
# every other CVE. A quoted phrase asks for the words too.
_EXACT_RE = re.compile(
    r"\b(?:CVE-\d{4}-\d{4,}|BDU:\d{4}-\d+|PT-\d{4}-\d+|GHSA(?:-\w{4}){3})\b|\"", re.I
)

_MEANING_SQL = text(
    """
    WITH scope AS (
        SELECT a.id, a.search_tsv, 1 - (e.embedding <=> CAST(:vector AS vector)) AS sim
        FROM articles a
        JOIN sources s ON s.id = a.source_id
        JOIN article_embeddings e ON e.article_id = a.id AND e.model = :model
        WHERE vector_norm(e.embedding) > 0
          AND (:any_source OR a.source_id = ANY(:source_ids))
          AND (:any_category OR s.category = ANY(:categories))
          AND (:any_language OR a.language = ANY(:languages))
          AND (CAST(:since AS timestamptz) IS NULL OR a.published_at >= CAST(:since AS timestamptz))
          AND (CAST(:until AS timestamptz) IS NULL OR a.published_at < CAST(:until AS timestamptz))
    ),
    stats AS (SELECT avg(sim) AS mean, stddev_pop(sim) AS std, count(*) AS n FROM scope)
    SELECT scope.id
    FROM scope, stats
    WHERE stats.n >= :min_scope AND stats.std > 0
      AND scope.sim >= :floor AND (scope.sim - stats.mean) / stats.std >= :min_z
      AND NOT (scope.search_tsv @@ websearch_to_tsquery('russian', :query))
    ORDER BY scope.sim DESC
    LIMIT :limit
    """
)


@dataclass(frozen=True, slots=True)
class Meaning:
    """What finds articles by meaning: the query's vector and the model's floor."""

    vector: list[float]
    model: str
    floor: float


def wants_exact(query: str) -> bool:
    return bool(_EXACT_RE.search(query))


async def by_meaning(session: AsyncSession, flt: ArticleFilter, meaning: Meaning) -> list[int]:
    """Articles close to the query in meaning that its words did not find."""
    result = await session.execute(
        _MEANING_SQL,
        {
            "vector": str(meaning.vector),
            "model": meaning.model,
            "query": flt.query or "",
            "floor": meaning.floor,
            "min_z": MEANING_MIN_Z,
            "min_scope": MEANING_MIN_SCOPE,
            "limit": MEANING_LIMIT,
            "any_source": not flt.source_ids,
            "source_ids": list(flt.source_ids),
            "any_category": not flt.categories,
            "categories": list(flt.categories),
            "any_language": not flt.languages,
            "languages": list(flt.languages),
            "since": flt.since,
            "until": flt.until,
        },
    )
    return [row[0] for row in result.all()]


async def find_articles(
    session: AsyncSession,
    flt: ArticleFilter,
    limit: int,
    offset: int,
    meaning: Meaning | None,
) -> tuple[list[tuple[Article, bool]], int]:
    """A page of articles: those the words find, by rank, then those found by
    meaning only. Each comes with whether it was found by meaning.

    Ranks are not merged into one score: an article with the words of the
    query comes first, and the closest by meaning follow in their own order.
    """
    by_words, words_total = await list_articles(session, flt, limit, offset)
    extra: list[int] = []
    if meaning is not None and flt.query and not wants_exact(flt.query):
        extra = await by_meaning(session, flt, meaning)
    total = words_total + len(extra)
    page = [(article, False) for article in by_words]
    room = limit - len(page)
    start = max(0, offset - words_total)
    wanted = extra[start : start + room] if room > 0 else []
    if wanted:
        rows = await session.execute(select(Article).where(Article.id.in_(wanted)))
        found = {article.id: article for article in rows.scalars().all()}
        page += [(found[article_id], True) for article_id in wanted if article_id in found]
    return page, total


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
