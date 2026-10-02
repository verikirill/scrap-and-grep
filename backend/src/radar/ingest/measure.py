"""Pages read again for what the feed did not carry: the length of the full
text, for the reading time, and the picture.

Most feeds give a teaser, and many give no picture. An article a reader
actually sees in the feed or a digest has its page read once, in the
background, for whichever of the two is missing; the next view shows them.
The claim is one UPDATE, so two workers never read the same page, and a page
that failed is not asked again for a few days.
"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import and_, func, or_, update

from radar.config import get_settings
from radar.db import session_scope
from radar.db.models import Article
from radar.images.extract import from_page
from radar.ingest import telegram
from radar.ingest.fetch import Ladder
from radar.ingest.net import build_client
from radar.ingest.pages import page_text
from radar.logging import get_logger
from radar.reading import word_count

log = get_logger(__name__)

MEASURE_BATCH = 30
PAGE_MAX_BYTES = 3_000_000
REMEASURE_AFTER = timedelta(days=3)
# A page that had no picture is unlikely to get one: asked again only after a month.
PICTURE_RECHECK_AFTER = timedelta(days=30)


async def _claim(ids: Sequence[int], now: datetime) -> list[tuple[int, str, bool, bool]]:
    """The articles to read, with what each lacks: the length, the picture."""
    picture_due = and_(
        Article.image_url.is_(None),
        or_(
            Article.image_checked_at.is_(None),
            Article.image_checked_at < now - PICTURE_RECHECK_AFTER,
        ),
    )
    async with session_scope() as session:
        result = await session.execute(
            update(Article)
            .where(
                Article.id.in_(list(ids)[:MEASURE_BATCH]),
                or_(Article.word_count.is_(None), picture_due),
                or_(Article.measured_at.is_(None), Article.measured_at < now - REMEASURE_AFTER),
            )
            .values(measured_at=now)
            .returning(Article.id, Article.url, Article.word_count.is_(None), picture_due)
        )
        return [(row[0], row[1], bool(row[2]), bool(row[3])) for row in result.all()]


@dataclass(frozen=True, slots=True)
class _Found:
    words: int | None = None
    picture: str | None = None
    # The page was read and asked for a picture, found or not.
    looked_for_picture: bool = False


async def _read(
    client: httpx.AsyncClient, url: str, *, needs_words: bool, needs_picture: bool
) -> _Found:
    if telegram.is_post_url(url):
        # The post is stored whole, and its page's og:image is the channel's
        # avatar: the post's own picture is on the page that embeds it.
        if not needs_picture:
            return _Found()
        return _Found(picture=await telegram.post_picture(client, url), looked_for_picture=True)
    ladder = Ladder(client)
    response = await ladder.get(
        url, max_bytes=PAGE_MAX_BYTES, expect="article" if needs_words else "page"
    )
    response.raise_for_status()
    text = await asyncio.to_thread(page_text, url, response.text) if needs_words else None
    picture = from_page(response.text, url) if needs_picture else None
    return _Found(word_count(text), picture, looked_for_picture=needs_picture)


async def measure(ids: Sequence[int], *, now: datetime | None = None) -> int:
    """Read the pages of these articles that are not timed yet. Returns how
    many got a length."""
    now = now or datetime.now(UTC)
    claimed = await _claim(ids, now)
    if not claimed:
        return 0
    slots = asyncio.Semaphore(get_settings().fulltext_concurrency)

    async def one(
        client: httpx.AsyncClient, url: str, needs_words: bool, needs_picture: bool
    ) -> _Found:
        async with slots:
            try:
                return await _read(
                    client, url, needs_words=needs_words, needs_picture=needs_picture
                )
            except Exception as exc:
                log.info("measure_failed", url=url, error=type(exc).__name__)
                return _Found()

    async with build_client() as client:
        found = await asyncio.gather(
            *(one(client, url, words, picture) for _, url, words, picture in claimed)
        )
    timed = 0
    async with session_scope() as session:
        for (article_id, *_), result in zip(claimed, found, strict=True):
            values: dict[str, object] = {}
            if result.words is not None:
                values["word_count"] = result.words
                timed += 1
            if result.looked_for_picture:
                # A miss is remembered too, so the page is not read for it again soon.
                values["image_checked_at"] = now
            if result.picture is not None:
                # One found meanwhile, by the reader or a post, is kept.
                values["image_url"] = func.coalesce(Article.image_url, result.picture)
            if values:
                await session.execute(
                    update(Article).where(Article.id == article_id).values(**values)
                )
    log.info("articles_measured", asked=len(ids), read=len(claimed), timed=timed)
    return timed
