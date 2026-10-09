"""The picture of each source: a channel's avatar, a site's icon.

A Telegram channel's page says its avatar in og:image. A site names its icons
in <link rel="apple-touch-icon"> and <link rel="icon">; the largest raster one
wins, then /favicon.ico. A site that turns bots away (SecurityLab answers 401)
gets its icon from Google's favicon service, which has fetched it already.
Habr's company blogs carry Habr's own icon, so the company's site is asked
instead. An icon under 32 px is not taken: the initials read better than a
blurred 16-pixel square.

The picture is cut to a square, scaled to 96 px and stored as WebP: what a
page shows is our file, never the source's address.
"""

import asyncio
import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html import unescape
from io import BytesIO
from urllib.parse import urljoin, urlsplit

import httpx
from PIL import IcoImagePlugin, Image, ImageOps, UnidentifiedImageError
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from radar.db.models import Source
from radar.images.store import ImageStore
from radar.ingest.net import safe_get
from radar.ingest.telegram import parse_channel
from radar.logging import get_logger

log = get_logger(__name__)

SIZE = 96
# Below this an icon is not scaled up, it is set in the middle as it is:
# a 16-pixel favicon blown up to a circle is a smudge.
SHARP_SIZE = 32
# Big enough to stop looking; at most this many addresses are tried.
GOOD_SIZE = 64
MAX_CANDIDATES = 6
MIN_SIZE = 16
# kaspersky.ru sends 1.4 MB of HTML before its icons.
MAX_PAGE_BYTES = 3_000_000
MAX_IMAGE_BYTES = 1_000_000
# A source with no picture is asked again after this, a changed one is not
# chased sooner: avatars change rarely.
RECHECK_AFTER = timedelta(days=30)
PER_RUN = 25
# The whole catalogue and then some, for the first run of a fresh stack.
AT_START = 500
CONCURRENCY = 4
GOOGLE_FAVICONS = "https://www.google.com/s2/favicons?sz=128&domain={host}"
# Habr's company blogs: the company's own site has its logo.
HABR_COMPANIES = {
    "pt": "https://ptsecurity.com",
    "kaspersky": "https://www.kaspersky.ru",
    "solarsecurity": "https://rt-solar.ru",
    "bizone": "https://bi.zone",
    "infowatch": "https://www.infowatch.ru",
    "f6": "https://www.f6.ru",
}

_OG_IMAGE_RE = re.compile(
    r"<meta[^>]+property=[\"']og:image[\"'][^>]+content=[\"']([^\"']+)[\"']", re.IGNORECASE
)
_LINK_RE = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
_ATTR_RE = re.compile(r"([a-z-]+)\s*=\s*[\"']([^\"']*)[\"']", re.IGNORECASE)
_HABR_COMPANY_RE = re.compile(r"habr\.com/(?:ru/|en/)?compan(?:y|ies)/([\w-]+)")


@dataclass(frozen=True, slots=True)
class Icon:
    url: str
    size: int
    preferred: bool


def avatar_key(source_id: int) -> str:
    """The picture's name in the image store, which takes hashed names only."""
    return (
        hashlib.sha1(f"source-avatar:{source_id}".encode(), usedforsecurity=False).hexdigest()
        + ".webp"
    )


def page_for(source: Source) -> str | None:
    """The page that says where the source's picture is."""
    if source.kind == "telegram":
        return f"https://t.me/{parse_channel(source.feed_url)}"
    site = source.site_url or source.feed_url
    company = _HABR_COMPANY_RE.search(site)
    if company and company.group(1) in HABR_COMPANIES:
        return HABR_COMPANIES[company.group(1)]
    parts = urlsplit(site)
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else None


def icons_in(page: str, base: str) -> list[str]:
    """Picture addresses a page offers, the most promising first."""
    found = [unescape(match) for match in _OG_IMAGE_RE.findall(page)] if "t.me/" in base else []
    icons = []
    for tag in _LINK_RE.findall(page):
        attributes = {key.lower(): value for key, value in _ATTR_RE.findall(tag)}
        rel = attributes.get("rel", "").lower()
        href = attributes.get("href", "")
        if "icon" not in rel or not href or href.startswith("data:") or href.endswith(".svg"):
            continue
        sizes = [int(size) for size in re.findall(r"(\d+)x\d+", attributes.get("sizes", ""))]
        icons.append(
            Icon(urljoin(base, unescape(href)), max(sizes, default=0), "apple-touch" in rel)
        )
    icons.sort(key=lambda icon: (icon.preferred, icon.size), reverse=True)
    parts = urlsplit(base)
    root = f"{parts.scheme}://{parts.netloc}"
    # Many sites serve the touch icon at its usual path without naming it.
    usual = [f"{root}/apple-touch-icon.png", f"{root}/favicon.ico"]
    return [*found, *(icon.url for icon in icons), *usual]


def square(data: bytes) -> tuple[bytes, int] | None:
    """The picture as a 96 px WebP square and the size it had, or None if it
    is not a picture or too small."""
    try:
        opened = Image.open(BytesIO(data))
        # An .ico holds several sizes; the largest is the one worth having.
        image: Image.Image = (
            opened.ico.getimage(max(opened.ico.sizes()))
            if isinstance(opened, IcoImagePlugin.IcoImageFile)
            else opened
        )
        image.load()
    except UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError:
        return None
    if min(image.size) < MIN_SIZE:
        return None
    image = image.convert("RGBA")
    if min(image.size) < SHARP_SIZE:
        # A small favicon keeps its pixels: doubled without blending, set in the middle.
        small = image.resize((image.width * 2, image.height * 2), Image.Resampling.NEAREST)
        canvas = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))
        canvas.paste(small, ((SIZE - small.width) // 2, (SIZE - small.height) // 2))
        fitted = canvas
    else:
        # Contained, not cropped: a wide logo keeps its ends.
        fitted = ImageOps.pad(image, (SIZE, SIZE), color=(255, 255, 255, 0))
    output = BytesIO()
    fitted.save(output, format="WEBP", quality=90)
    return output.getvalue(), min(image.size)


async def _picture(client: httpx.AsyncClient, url: str) -> tuple[bytes, int] | None:
    try:
        response = await safe_get(client, url, max_bytes=MAX_IMAGE_BYTES)
    except Exception:
        return None
    if response.status_code != httpx.codes.OK:
        return None
    return square(response.content)


async def find_avatar(client: httpx.AsyncClient, source: Source) -> bytes | None:
    page = page_for(source)
    if page is None:
        return None
    candidates: list[str] = []
    try:
        response = await safe_get(client, page, max_bytes=MAX_PAGE_BYTES)
        if response.status_code == httpx.codes.OK:
            candidates = icons_in(response.text, str(response.url) or page)
    except Exception as exc:
        log.info("avatar_page_failed", source=source.slug, error=type(exc).__name__)
    if source.kind != "telegram":
        candidates.append(GOOGLE_FAVICONS.format(host=urlsplit(page).hostname))
    # The largest picture wins; one big enough ends the search.
    best: tuple[bytes, int] | None = None
    for url in list(dict.fromkeys(candidates))[:MAX_CANDIDATES]:
        picture = await _picture(client, url)
        if picture is not None and (best is None or picture[1] > best[1]):
            best = picture
        if best is not None and best[1] >= GOOD_SIZE:
            break
    return best[0] if best else None


async def refresh_avatars(
    session: AsyncSession, client: httpx.AsyncClient, store: ImageStore, *, limit: int = PER_RUN
) -> int:
    """Find pictures for sources that have none or were last looked at long ago;
    the number found."""
    now = datetime.now(UTC)
    sources = list(
        await session.scalars(
            select(Source)
            .where(
                or_(
                    Source.avatar_checked_at.is_(None),
                    Source.avatar_checked_at < now - RECHECK_AFTER,
                )
            )
            .order_by(Source.avatar_checked_at.nulls_first(), Source.id)
            .limit(limit)
        )
    )
    slots = asyncio.Semaphore(CONCURRENCY)

    async def one(source: Source) -> bytes | None:
        async with slots:
            return await find_avatar(client, source)

    pictures = await asyncio.gather(*(one(source) for source in sources))
    found = 0
    for source, picture in zip(sources, pictures, strict=True):
        source.avatar_checked_at = now
        if picture is None:
            continue
        await store.put(avatar_key(source.id), picture)
        source.avatar_updated_at = now
        found += 1
    log.info("avatars_refreshed", checked=len(sources), found=found)
    return found
