"""Finding an article's picture and keeping a copy when a link is not enough."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx

from radar.db.models import Article
from radar.images.extract import from_page, usable
from radar.images.store import ImageStore
from radar.ingest.net import safe_get
from radar.logging import get_logger

log = get_logger(__name__)

PAGE_MAX_BYTES = 2_000_000
IMAGE_MAX_BYTES = 8_000_000
# A page without a picture is not asked again for a while.
RECHECK_AFTER = timedelta(days=3)
_SIGNATURES = (
    (b"\xff\xd8\xff", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
)


@dataclass(frozen=True, slots=True)
class Picture:
    data: bytes
    extension: str

    @property
    def content_type(self) -> str:
        return {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp", "gif": "image/gif"}[
            self.extension
        ]


class NotAPicture(ValueError):
    """The address answered with something other than a raster picture."""


def sniff(data: bytes) -> str | None:
    """The format by its first bytes; the Content-Type header is not trusted."""
    for signature, extension in _SIGNATURES:
        if data.startswith(signature):
            return extension
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def image_key(url: str, extension: str) -> str:
    return f"{hashlib.sha256(url.encode()).hexdigest()[:40]}.{extension}"


async def download(client: httpx.AsyncClient, url: str) -> Picture:
    response = await safe_get(client, url, max_bytes=IMAGE_MAX_BYTES, headers={"Accept": "image/*"})
    response.raise_for_status()
    extension = sniff(response.content)
    if extension is None:
        raise NotAPicture(url)
    return Picture(response.content, extension)


async def find_page_image(client: httpx.AsyncClient, url: str) -> str | None:
    response = await safe_get(client, url, max_bytes=PAGE_MAX_BYTES)
    response.raise_for_status()
    return from_page(response.text, url)


async def ensure_image_url(
    article: Article, client: httpx.AsyncClient, *, now: datetime | None = None
) -> str | None:
    """The article's picture address, looked up on its page if the feed had
    none. Updates the row; the caller commits."""
    if article.image_url:
        # Rows stored before a stand-in pattern was known lose it here.
        if usable(article.image_url):
            return article.image_url
        article.image_url = None
        article.image_key = None
    now = now or datetime.now(UTC)
    if article.image_checked_at and now - article.image_checked_at < RECHECK_AFTER:
        return None
    article.image_checked_at = now
    try:
        article.image_url = await find_page_image(client, article.url)
    except Exception as exc:
        log.info("page_image_failed", url=article.url, error=f"{type(exc).__name__}"[:100])
        return None
    return article.image_url


async def mirror(article: Article, client: httpx.AsyncClient, store: ImageStore) -> Picture | None:
    """A stored copy of the article's picture, made on first need."""
    if not article.image_url:
        return None
    if article.image_key:
        data = await store.get(article.image_key)
        if data is not None:
            return Picture(data, article.image_key.rsplit(".", 1)[1])
    try:
        picture = await download(client, article.image_url)
    except Exception as exc:
        log.info("image_download_failed", url=article.image_url, error=type(exc).__name__)
        return None
    key = image_key(article.image_url, picture.extension)
    await store.put(key, picture.data)
    article.image_key = key
    return picture
