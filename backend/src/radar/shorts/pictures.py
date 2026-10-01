"""The pictures of the news in a video: each article's own, stored once.

The renderer gets the bytes, not addresses: its browser has no route to the
internet, and a news site may refuse a hotlink anyway. A video without a
picture is still a video, so nothing here fails the render.
"""

import asyncio
from collections.abc import Awaitable, Callable, Sequence

from sqlalchemy import select

from radar.db import session_scope
from radar.db.models import Article
from radar.images.service import Picture, ensure_image_url, mirror
from radar.images.store import get_image_store
from radar.ingest.net import build_client
from radar.logging import get_logger

log = get_logger(__name__)

# The renderer refuses larger ones (MAX_PICTURE_BYTES in shorts/server/request.ts).
MAX_PICTURE_BYTES = 3_000_000
# A GIF would animate on the browser's clock, not the video's.
STILL_FORMATS = frozenset({"jpg", "png", "webp"})
PICTURE_TIMEOUT_SECONDS = 30.0

Fetch = Callable[[Article], Awaitable[Picture | None]]


async def pictures_for(articles: Sequence[Article | None], fetch: Fetch) -> list[Picture | None]:
    """One picture per article, in order; None where there is none to show."""

    async def one(article: Article | None) -> Picture | None:
        if article is None:
            return None
        try:
            picture = await asyncio.wait_for(fetch(article), PICTURE_TIMEOUT_SECONDS)
        # A slow site, a broken store or a refused download all mean the
        # same for the video: this item goes without a picture.
        except Exception as exc:
            log.info("short_picture_failed", article_id=article.id, error=type(exc).__name__)
            return None
        if picture is None or picture.extension not in STILL_FORMATS:
            return None
        return picture if len(picture.data) <= MAX_PICTURE_BYTES else None

    return list(await asyncio.gather(*(one(article) for article in articles)))


async def beat_pictures(article_ids: Sequence[int]) -> list[Picture | None]:
    """The pictures of the video's news items, found and stored on first need."""
    store = get_image_store()
    async with session_scope() as session, build_client() as client:
        rows = await session.scalars(select(Article).where(Article.id.in_(article_ids)))
        found = {article.id: article for article in rows}

        async def fetch(article: Article) -> Picture | None:
            if not await ensure_image_url(article, client):
                return None
            return await mirror(article, client, store)

        # The rows are updated with what was found; the scope commits them.
        return await pictures_for([found.get(article_id) for article_id in article_ids], fetch)
