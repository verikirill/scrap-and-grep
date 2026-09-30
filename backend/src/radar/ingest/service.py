"""Ingestion use cases: pull one source, pull all, embed what is new."""

import asyncio
from dataclasses import dataclass, replace
from datetime import UTC, datetime

import httpx
import trafilatura
from sqlalchemy import select

from radar.ai.embedder import Embedder
from radar.cache import Cache
from radar.config import get_settings
from radar.db import session_scope
from radar.db.models import Source
from radar.ingest.feeds import CONTENT_LIMIT, FeedResult, fetch_feed
from radar.ingest.net import safe_get
from radar.logging import get_logger
from radar.store import articles as article_store
from radar.store.articles import NewArticle
from radar.text import content_hash

log = get_logger(__name__)

LOCK_TTL_SECONDS = 300
FULLTEXT_PER_RUN = 40
FULLTEXT_MAX_BYTES = 3_000_000
EMBED_CHUNK = 256


@dataclass(frozen=True, slots=True)
class IngestReport:
    source_id: int
    status: str
    new_articles: int = 0
    error: str | None = None


async def ingest_source(source_id: int, client: httpx.AsyncClient, cache: Cache) -> IngestReport:
    """Fetch one feed and store the articles that are new.

    A per-source lock stops two workers from fetching the same feed at once.
    Everything after the fetch is idempotent, so an at-least-once queue can
    redeliver this task safely.
    """
    async with cache.lock(f"ingest:{source_id}", LOCK_TTL_SECONDS) as acquired:
        if not acquired:
            return IngestReport(source_id, "skipped_locked")
        async with session_scope() as session:
            source = await session.get(Source, source_id)
            if source is None or not source.enabled:
                return IngestReport(source_id, "skipped_disabled")
            feed_url, language = source.feed_url, source.language
            etag, last_modified, full_text = (
                source.etag,
                source.last_modified,
                source.fetch_full_text,
            )

        try:
            feed = await fetch_feed(
                client, feed_url, language=language, etag=etag, last_modified=last_modified
            )
            new_ids = await _store(source_id, feed, client, full_text)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"[:500]
            log.warning("ingest_failed", source_id=source_id, error=error)
            await _record(source_id, status="error", error=error)
            return IngestReport(source_id, "error", error=error)

        await _record(source_id, status=feed.status, feed=feed)
        log.info("ingest_done", source_id=source_id, status=feed.status, new=len(new_ids))
        return IngestReport(source_id, feed.status, new_articles=len(new_ids))


async def _store(
    source_id: int, feed: FeedResult, client: httpx.AsyncClient, full_text: bool
) -> list[int]:
    if feed.status != "ok" or not feed.articles:
        return []
    async with session_scope() as session:
        known = await article_store.known_urls(session, [item.url for item in feed.articles])
    fresh = [item for item in feed.articles if item.url not in known]
    if full_text:
        fresh = await _with_full_text(fresh, client)
    async with session_scope() as session:
        return await article_store.insert_new(session, source_id, fresh)


async def _with_full_text(items: list[NewArticle], client: httpx.AsyncClient) -> list[NewArticle]:
    """Download article pages for feeds that only carry a teaser.

    Capped per run and bounded in concurrency: the goal is a usable summary,
    not a crawl. A page that fails to load leaves the teaser in place.
    """
    newest = sorted(items, key=lambda item: item.published_at, reverse=True)[:FULLTEXT_PER_RUN]
    wanted = {item.url for item in newest if not item.content}
    slots = asyncio.Semaphore(get_settings().fulltext_concurrency)

    async def enrich(item: NewArticle) -> NewArticle:
        if item.url not in wanted:
            return item
        async with slots:
            try:
                response = await safe_get(client, item.url, max_bytes=FULLTEXT_MAX_BYTES)
                response.raise_for_status()
                text = await asyncio.to_thread(
                    trafilatura.extract, response.text, include_comments=False, include_tables=False
                )
            except Exception as exc:
                log.info(
                    "fulltext_failed", url=item.url, error=f"{type(exc).__name__}: {exc}"[:200]
                )
                return item
        if not text or len(text) < 200:
            return item
        body = text[:CONTENT_LIMIT]
        return replace(item, content=body, content_hash=content_hash(item.title, body))

    return list(await asyncio.gather(*(enrich(item) for item in items)))


async def _record(
    source_id: int, *, status: str, feed: FeedResult | None = None, error: str | None = None
) -> None:
    async with session_scope() as session:
        source = await session.get(Source, source_id)
        if source is None:
            return
        source.last_fetched_at = datetime.now(UTC)
        source.last_status = status
        source.last_error = error
        source.consecutive_failures = source.consecutive_failures + 1 if error else 0
        if feed is not None and feed.status == "ok":
            source.etag = feed.etag
            source.last_modified = feed.last_modified


async def enabled_source_ids() -> list[int]:
    async with session_scope() as session:
        result = await session.execute(select(Source.id).where(Source.enabled).order_by(Source.id))
        return [row[0] for row in result.all()]


async def embed_pending(
    embedder: Embedder,
    *,
    max_articles: int = 5000,
    since: datetime | None = None,
    until: datetime | None = None,
) -> int:
    """Embed articles that have no vector for the active model. Returns the count."""
    done = 0
    while done < max_articles:
        async with session_scope() as session:
            batch = await article_store.pending_embeddings(
                session, embedder.model_id, min(EMBED_CHUNK, max_articles - done), since, until
            )
        if not batch:
            break
        vectors = await embedder.embed([text for _, text in batch], "document")
        async with session_scope() as session:
            await article_store.save_embeddings(
                session,
                embedder.model_id,
                [
                    (article_id, vector)
                    for (article_id, _), vector in zip(batch, vectors, strict=True)
                ],
            )
        done += len(batch)
    return done
