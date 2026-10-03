"""Ingestion use cases: pull one source, pull all, embed what is new."""

import asyncio
import random
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import or_, select

from radar.ai.embedder import Embedder
from radar.cache import Cache
from radar.config import get_settings
from radar.db import session_scope
from radar.db.models import Source
from radar.images.extract import from_page
from radar.ingest.feeds import CONTENT_LIMIT, FeedResult, fetch_feed
from radar.ingest.fetch import Ladder, Outcome
from radar.ingest.health import error_kind, record_poll
from radar.ingest.pages import fetch_listing, page_text
from radar.ingest.polite import robots_allows
from radar.ingest.ptsecurity import fetch_trending
from radar.ingest.telegram import fetch_channel
from radar.ingest.wordpress import fetch_posts
from radar.logging import get_logger
from radar.reading import word_count
from radar.store import articles as article_store
from radar.store.articles import NewArticle
from radar.text import content_hash

log = get_logger(__name__)

LOCK_TTL_SECONDS = 300
FULLTEXT_PER_RUN = 40
FULLTEXT_MAX_BYTES = 3_000_000
EMBED_CHUNK = 256
# A source failing again and again is polled less and less often.
BACKOFF_BASE = timedelta(minutes=15)
BACKOFF_MAX = timedelta(hours=24)


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
            kind, feed_url, language = source.kind, source.feed_url, source.language
            etag, last_modified, full_text = (
                source.etag,
                source.last_modified,
                source.fetch_full_text,
            )
            last_post_id, selector = source.last_post_id, source.link_selector
            ladder = Ladder(client, remembered=source.fetch_method, proxy=source.proxy_url)

        robots = None
        try:
            if kind != "telegram":
                # Recorded, not obeyed: see ingest/polite.py.
                robots = await robots_allows(ladder.client, feed_url)
            if kind == "telegram":
                feed = await fetch_channel(
                    ladder.client, feed_url, language=language, last_post_id=last_post_id
                )
            elif kind == "pt_trending":
                feed = await fetch_trending(
                    ladder, feed_url, etag=etag, last_modified=last_modified
                )
            elif kind == "wordpress":
                feed = await fetch_posts(
                    ladder, feed_url, language=language, etag=etag, last_modified=last_modified
                )
            elif kind == "page":
                feed = await fetch_listing(
                    ladder,
                    feed_url,
                    language=language,
                    selector=selector,
                    etag=etag,
                    last_modified=last_modified,
                    known=_known_urls,
                )
            else:
                feed = await fetch_feed(
                    ladder, feed_url, language=language, etag=etag, last_modified=last_modified
                )
            new_ids = await _store(source_id, feed, ladder, full_text)
        except Exception as exc:
            await ladder.aclose()
            error = f"{type(exc).__name__}: {exc}"[:500]
            kind = error_kind(exc)
            log.warning("ingest_failed", source_id=source_id, error=error, kind=kind)
            await _record(
                source_id,
                status="error",
                error=error,
                kind=kind,
                read=ladder.first,
                robots=robots,
            )
            return IngestReport(source_id, "error", error=error)

        await ladder.aclose()
        await _record(
            source_id,
            status=feed.status,
            feed=feed,
            new=len(new_ids),
            read=ladder.first,
            robots=robots,
        )
        log.info("ingest_done", source_id=source_id, status=feed.status, new=len(new_ids))
        return IngestReport(source_id, feed.status, new_articles=len(new_ids))


async def _known_urls(urls: list[str]) -> set[str]:
    async with session_scope() as session:
        return await article_store.known_urls(session, urls)


async def _store(source_id: int, feed: FeedResult, ladder: Ladder, full_text: bool) -> list[int]:
    if feed.status != "ok" or not feed.articles:
        return []
    async with session_scope() as session:
        known = await article_store.known_urls(session, [item.url for item in feed.articles])
    fresh = [item for item in feed.articles if item.url not in known]
    if full_text:
        fresh = await _with_full_text(fresh, ladder)
    async with session_scope() as session:
        return await article_store.insert_new(session, source_id, fresh)


async def _with_full_text(items: list[NewArticle], ladder: Ladder) -> list[NewArticle]:
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
                response = await ladder.get(
                    item.url, max_bytes=FULLTEXT_MAX_BYTES, expect="article"
                )
                response.raise_for_status()
                text = await asyncio.to_thread(page_text, item.url, response.text)
            except Exception as exc:
                log.info(
                    "fulltext_failed", url=item.url, error=f"{type(exc).__name__}: {exc}"[:200]
                )
                return item
        # The page is here anyway: its og:image is the story's picture when
        # the feed carried none.
        image_url = item.image_url or from_page(response.text, item.url)
        if not text or len(text) < 200:
            return replace(item, image_url=image_url)
        body = text[:CONTENT_LIMIT]
        return replace(
            item,
            content=body,
            content_hash=content_hash(item.title, body),
            image_url=image_url,
            word_count=word_count(text),
        )

    return list(await asyncio.gather(*(enrich(item) for item in items)))


async def _record(
    source_id: int,
    *,
    status: str,
    feed: FeedResult | None = None,
    error: str | None = None,
    kind: str | None = None,
    new: int = 0,
    read: Outcome | None = None,
    robots: bool | None = None,
) -> None:
    async with session_scope() as session:
        source = await session.get(Source, source_id)
        if source is None:
            return
        await record_poll(session, source_id, status=status, kind=kind, new=new)
        source.last_fetched_at = datetime.now(UTC)
        source.last_status = status
        source.last_error = error
        source.consecutive_failures = source.consecutive_failures + 1 if error else 0
        source.retry_at = (
            source.last_fetched_at + backoff(source.consecutive_failures) if error else None
        )
        if robots is not None:
            source.robots_allowed = robots
        if feed is not None and feed.status == "ok":
            source.etag = feed.etag
            source.last_modified = feed.last_modified
        if read is not None and read.step:
            # Kept on failure too: a site that refused every step this time
            # is tried from the same step next time.
            if read.step != source.fetch_method:
                source.fetch_changed_at = source.last_fetched_at
                source.fetch_note = read.note
            elif read.note:
                source.fetch_note = read.note
            # A run that starts on the remembered step and is let in there
            # keeps the reason the source was moved up to it.
            source.fetch_method = read.step
            source.fetch_via_proxy = read.proxy is not None
        if feed is not None and feed.last_post_id is not None:
            # Written after the posts are stored: a failed run reads them again.
            source.last_post_id = feed.last_post_id


def backoff(failures: int) -> timedelta:
    """How long a source that failed `failures` times in a row is left alone.

    One failure is let pass: the next scheduled run tries again. From the
    second on the pause doubles, from one poll interval up to a day, with a
    fifth of it at random so that sources failing together drift apart.
    """
    if failures < 2:
        return timedelta(0)
    pause: timedelta = min(BACKOFF_BASE * 2 ** (failures - 2), BACKOFF_MAX)
    return pause * (0.9 + random.random() / 5)  # noqa: S311


async def enabled_source_ids(now: datetime | None = None) -> list[int]:
    """Sources to poll: enabled, and not resting after a series of failures.

    A source an administrator refreshes by hand is read at once all the same.
    """
    moment = now or datetime.now(UTC)
    async with session_scope() as session:
        result = await session.execute(
            select(Source.id)
            .where(Source.enabled, or_(Source.retry_at.is_(None), Source.retry_at <= moment))
            .order_by(Source.id)
        )
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
