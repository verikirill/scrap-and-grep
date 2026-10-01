"""Pages read again for what the feed did not carry: the length of the full
text, for the reading time, and the picture.

Most feeds give a teaser. An article a reader actually sees in the feed or a
digest has its page read once, in the background; the next view shows its
reading time. The claim is one UPDATE, so two workers never read the same
page, and a page that failed is not asked again for a few days.
"""

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import or_, update

from radar.config import get_settings
from radar.db import session_scope
from radar.db.models import Article
from radar.images.extract import from_page
from radar.ingest.net import build_client, safe_get
from radar.ingest.pages import page_text
from radar.logging import get_logger
from radar.reading import word_count

log = get_logger(__name__)

MEASURE_BATCH = 30
PAGE_MAX_BYTES = 3_000_000
REMEASURE_AFTER = timedelta(days=3)


async def _claim(ids: Sequence[int], now: datetime) -> list[tuple[int, str, str | None]]:
    async with session_scope() as session:
        result = await session.execute(
            update(Article)
            .where(
                Article.id.in_(list(ids)[:MEASURE_BATCH]),
                Article.word_count.is_(None),
                or_(Article.measured_at.is_(None), Article.measured_at < now - REMEASURE_AFTER),
            )
            .values(measured_at=now)
            .returning(Article.id, Article.url, Article.image_url)
        )
        return [(row[0], row[1], row[2]) for row in result.all()]


async def _read(
    client: httpx.AsyncClient, url: str, has_picture: bool
) -> tuple[int | None, str | None]:
    response = await safe_get(client, url, max_bytes=PAGE_MAX_BYTES)
    response.raise_for_status()
    text = await asyncio.to_thread(page_text, url, response.text)
    picture = None if has_picture else from_page(response.text, url)
    return word_count(text), picture


async def measure(ids: Sequence[int], *, now: datetime | None = None) -> int:
    """Read the pages of these articles that are not timed yet. Returns how
    many got a length."""
    now = now or datetime.now(UTC)
    claimed = await _claim(ids, now)
    if not claimed:
        return 0
    slots = asyncio.Semaphore(get_settings().fulltext_concurrency)

    async def one(
        client: httpx.AsyncClient, url: str, has_picture: bool
    ) -> tuple[int | None, str | None]:
        async with slots:
            try:
                return await _read(client, url, has_picture)
            except Exception as exc:
                log.info("measure_failed", url=url, error=type(exc).__name__)
                return None, None

    async with build_client() as client:
        found = await asyncio.gather(
            *(one(client, url, image is not None) for _, url, image in claimed)
        )
    timed = 0
    async with session_scope() as session:
        for (article_id, _, _), (words, picture) in zip(claimed, found, strict=True):
            values: dict[str, object] = {}
            if words is not None:
                values["word_count"] = words
                timed += 1
            if picture is not None:
                values["image_url"], values["image_checked_at"] = picture, now
            if values:
                await session.execute(
                    update(Article).where(Article.id == article_id).values(**values)
                )
    log.info("articles_measured", asked=len(ids), read=len(claimed), timed=timed)
    return timed
