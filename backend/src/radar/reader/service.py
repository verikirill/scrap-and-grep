"""Reading an article's page once, when it is first opened, and its pictures
when the browser asks for them."""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast

import httpx
import trafilatura
from sqlalchemy import text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from trafilatura.settings import Document

from radar.cache import Cache
from radar.db.models import Article, ArticleBody
from radar.images.service import NotAPicture, Picture, download, image_key
from radar.images.store import ImageStore
from radar.ingest import bdu, telegram
from radar.ingest.net import ResponseTooLargeError, UnsafeUrlError, build_client, safe_get
from radar.logging import get_logger
from radar.reader.blocks import MIN_CHARS, Block, Body, from_text, from_tree, plain_text
from radar.reading import word_count

log = get_logger(__name__)

# Raised when the blocks change, so that pages read before are read again.
READER_VERSION = 1
PAGE_MAX_BYTES = 3_000_000
# A page that could not be read is tried again after this long.
RETRY_AFTER = timedelta(hours=6)
# A picture the site would not give is not asked for again for this long.
PICTURE_RETRY_SECONDS = 600
# Pages and pictures fetched at once by one API process; the rest wait.
_pages = asyncio.Semaphore(4)
_pictures = asyncio.Semaphore(8)
# What a site that is down, slow, closed or too big answers with, and an
# address that cannot be requested at all.
_UNREACHABLE = (
    httpx.HTTPError,
    httpx.InvalidURL,
    OSError,
    UnsafeUrlError,
    ResponseTooLargeError,
)
# Statuses whose blocks are the article's own text, read from its page or source.
_OWN_TEXT = {"page", "stored", "stale"}


class PictureUnavailable(Exception):
    """The site did not give the picture: gone, refused, or not a picture at all."""


@dataclass(frozen=True, slots=True)
class Reading:
    blocks: list[Block]
    # The whole text, or only the part of it the feed carried.
    complete: bool


async def open_article(session: AsyncSession, article: Article) -> Reading:
    """The article as the reader shows it, read from its page on first need."""
    row = await session.get(ArticleBody, article.id)
    now = datetime.now(UTC)
    if row is not None and _is_current(row, now):
        return Reading(cast(list[Block], row.blocks), _complete(row.status, article))
    # Nothing waits on the database while the page loads.
    await session.commit()
    body, status = await _read(article)
    if status == "failed" and row is not None and row.status in _OWN_TEXT:
        # Read again after a change of the reader, and the site failed this
        # time: the text read before beats the feed's until the next try.
        await session.execute(
            update(ArticleBody)
            .where(ArticleBody.article_id == article.id)
            .values(status="stale", read_at=now)
        )
        return Reading(cast(list[Block], row.blocks), complete=True)
    values = {
        "version": READER_VERSION,
        "status": status,
        "blocks": body.blocks,
        "images": body.images,
        "read_at": now,
    }
    # Stored copies of pictures stay: they are named by address, and a
    # picture the page still shows keeps its name.
    await session.execute(
        insert(ArticleBody)
        .values(article_id=article.id, **values)
        .on_conflict_do_update(index_elements=[ArticleBody.article_id], set_=values)
    )
    if status == "page" and article.word_count is None:
        article.word_count = word_count(plain_text(body.blocks))
    return Reading(body.blocks, _complete(status, article))


def _is_current(row: ArticleBody, now: datetime) -> bool:
    if row.status in {"failed", "stale"}:
        return now - row.read_at < RETRY_AFTER
    return row.version == READER_VERSION


def _complete(status: str, article: Article) -> bool:
    return status in _OWN_TEXT or article.word_count is not None


async def _read(article: Article) -> tuple[Body, str]:
    stored = _stored(article)
    # A Telegram post is all there is to read, as is a card of the
    # trending-vulnerabilities page; both are stored whole.
    if telegram.is_post_url(article.url) or article.source.kind == "pt_trending":
        return stored, "stored"
    async with _pages:
        try:
            async with build_client() as client:
                response = await safe_get(client, article.url, max_bytes=PAGE_MAX_BYTES)
            response.raise_for_status()
        except _UNREACHABLE as exc:
            log.info("reader_page_failed", url=article.url, error=type(exc).__name__)
            return stored, "failed"
        try:
            body = await asyncio.to_thread(_from_page, article, response.text)
        except Exception as exc:  # trafilatura and lxml on whatever a site serves
            log.warning("reader_page_unreadable", url=article.url, error=type(exc).__name__)
            return stored, "failed"
    if body is None or body.chars < MIN_CHARS:
        log.info("reader_page_empty", url=article.url)
        return stored, "failed"
    return body, "page"


def _from_page(article: Article, page: str) -> Body | None:
    if bdu.is_vulnerability_page(article.url):
        # The page is drawn in the browser from data in it; the text comes from that data.
        found = bdu.page_text(page)
        return from_text(found, title=article.title, lead=None, labelled=True) if found else None
    document = trafilatura.bare_extraction(
        page,
        url=article.url,
        include_comments=False,
        include_tables=True,
        include_images=True,
        include_formatting=True,
        include_links=True,
    )
    if not isinstance(document, Document) or document.body is None:
        return None
    return from_tree(document.body, title=article.title, lead=article.image_url)


def _stored(article: Article) -> Body:
    """What the feed or the channel gave: the text known without the page."""
    return from_text(
        article.content or article.summary or "", title=article.title, lead=article.image_url
    )


async def picture(
    session: AsyncSession, article_id: int, name: str, store: ImageStore, cache: Cache
) -> Picture | None:
    """A picture of an opened article, fetched once and kept.

    Only the addresses found in the article are fetched, so the endpoint is
    no general-purpose proxy.
    """
    row = await session.get(ArticleBody, article_id)
    if row is None or name not in row.images:
        return None
    if (key := row.image_keys.get(name)) and (kept := await _kept(store, key)):
        return kept
    url = row.images[name]
    await session.commit()
    refused = f"reader:picture-refused:{name}"
    if await cache.get_json(refused):
        raise PictureUnavailable(url)
    try:
        async with _pictures, build_client() as client:
            found = await download(client, url)
    except (*_UNREACHABLE, NotAPicture) as exc:
        await cache.set_json(refused, True, PICTURE_RETRY_SECONDS)
        raise PictureUnavailable(url) from exc
    key = image_key(url, found.extension)
    try:
        await store.put(key, found.data)
    except Exception as exc:  # a full disk, a read-only volume, S3 down
        # The copy is a convenience: the reader still gets the picture.
        log.warning("reader_picture_not_kept", error=type(exc).__name__)
        return found
    await session.execute(
        text(
            "UPDATE article_bodies SET image_keys = image_keys"
            " || jsonb_build_object(CAST(:name AS text), CAST(:key AS text))"
            " WHERE article_id = :article_id"
        ),
        {"name": name, "key": key, "article_id": article_id},
    )
    return found


async def _kept(store: ImageStore, key: str) -> Picture | None:
    try:
        data = await store.get(key)
    except Exception as exc:  # the site still has the picture
        log.warning("reader_picture_copy_unreadable", error=type(exc).__name__)
        return None
    return Picture(data, key.rsplit(".", 1)[1]) if data is not None else None
