"""What an article's page says, read the way the site allows; and sources
without a feed, read from their news page."""

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit, urlunsplit

import httpx
import trafilatura
from selectolax.lexbor import LexborHTMLParser

from radar.config import get_settings
from radar.images.extract import from_page
from radar.ingest import bdu, listing
from radar.ingest.feeds import CONTENT_LIMIT, SUMMARY_LIMIT, FeedResult
from radar.ingest.fetch import Ladder, is_js_shell
from radar.logging import get_logger
from radar.reading import word_count
from radar.store.articles import NewArticle
from radar.text import content_hash, detect_language, strip_html, truncate

log = get_logger(__name__)

# Article pages opened per run: the first run of a news page reads this
# many of its newest links, later runs only the new ones.
PAGES_PER_RUN = 20
ARTICLE_MAX_BYTES = 3_000_000
# Text shorter than this is no article's text but a teaser or a stub.
MIN_TEXT_CHARS = 200

Known = Callable[[list[str]], Awaitable[set[str]]]


class MarkupChanged(Exception):
    """A page that should list posts or entries has them, but none could be read."""


def page_text(url: str, page: str) -> str | None:
    """The readable text of the page at `url`, or None when there is none.

    Most pages are read by trafilatura. A BDU vulnerability is drawn in the
    browser from data in the page, so its text comes from that data.
    """
    if bdu.is_vulnerability_page(url):
        return bdu.page_text(page)
    return trafilatura.extract(page, include_comments=False, include_tables=False)


async def fetch_listing(
    ladder: Ladder,
    url: str,
    *,
    language: str,
    selector: str | None,
    etag: str | None,
    last_modified: str | None,
    known: Known,
) -> FeedResult:
    """The new articles a news page (or a sitemap) links to, each read from its page.

    The page is asked for with its validators, so an unchanged page costs
    a 304. A page whose links are not found on the light steps (a list drawn
    by script) is asked again a step up the ladder, up to the browser.
    """
    headers = {}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    response = await ladder.get(
        url,
        headers=headers,
        expect="page",
        wanted=lambda page: bool(listing.find_links(page.text, _base(url, page), selector)),
    )
    if response.status_code == 304:
        return FeedResult(status="not_modified", etag=etag, last_modified=last_modified)
    response.raise_for_status()
    base = _base(url, response)
    body = response.text
    if listing.is_sitemap(body) and "<sitemapindex" in body[:3000].lower():
        # An index of sitemaps: the newest, a news one first.
        children = listing.sitemap_children(body, base)
        if not children:
            raise MarkupChanged(f"no sitemaps in the index at {url}")
        child = await ladder.get(children[0], expect="any")
        child.raise_for_status()
        body, base = child.text, children[0]
    links = await asyncio.to_thread(listing.find_links, body, base, selector)
    if not links:
        raise MarkupChanged(f"no article links on {url}")
    seen = await known([link.url for link in links])
    fresh = [link for link in links if link.url not in seen][:PAGES_PER_RUN]
    slots = asyncio.Semaphore(get_settings().fulltext_concurrency)

    async def read(link: listing.Link) -> NewArticle | None:
        async with slots:
            return await _article(ladder, link, language)

    articles = await asyncio.gather(*(read(link) for link in fresh))
    return FeedResult(
        status="ok",
        articles=tuple(article for article in articles if article is not None),
        etag=response.headers.get("etag"),
        last_modified=response.headers.get("last-modified"),
    )


def _base(url: str, response: httpx.Response) -> str:
    """Where the page's links are relative to: where it ended, with the hash
    route it was asked for (a page drawn by script has no other address)."""
    final = str(response.request.url)
    route = urlsplit(url).fragment
    parts = urlsplit(final)
    if route and not parts.fragment:
        return urlunsplit((*parts[:4], route))
    return final


async def _article(ladder: Ladder, link: listing.Link, language: str) -> NewArticle | None:
    try:
        response = await ladder.get(link.url, max_bytes=ARTICLE_MAX_BYTES, expect="article")
        response.raise_for_status()
    except Exception as exc:
        log.info("page_article_failed", url=link.url, error=f"{type(exc).__name__}: {exc}"[:200])
        # The listing's own title keeps the story; its text is not to be had.
        return _from_link(link, language) if len(link.title) >= 12 else None
    return await asyncio.to_thread(article_from_page, link, response.text, language)


def _from_link(link: listing.Link, language: str) -> NewArticle:
    return NewArticle(
        url=link.url,
        title=truncate(link.title, 500),
        summary="",
        content=None,
        author=None,
        tags=(),
        language=language if language in {"ru", "en"} else detect_language(link.title),
        published_at=_not_ahead(link.published_at),
        content_hash=content_hash(link.title, ""),
    )


def article_from_page(link: listing.Link, page: str, language: str) -> NewArticle | None:
    """An article from its page: text by trafilatura, the date the page states."""
    if is_js_shell(page):
        # The browser did not draw it this time: read it next run.
        return None
    text = page_text(link.url, page) or ""
    meta = trafilatura.extract_metadata(page, default_url=link.url)
    heading = LexborHTMLParser(page[:2_000_000]).css_first("h1")
    page_title = (heading.text(separator=" ", strip=True) if heading is not None else "") or (
        meta.title if meta and meta.title else ""
    )
    # A listing may name a story by its number only ("PT-2026-104067").
    title = link.title if len(link.title.split()) >= 3 or not page_title else page_title
    title = " ".join(title.split())
    if not title:
        return None
    description = strip_html(meta.description or "") if meta else ""
    body = text if len(text) >= MIN_TEXT_CHARS else ""
    summary = truncate(description or body, SUMMARY_LIMIT)
    published = link.published_at or published_on_page(page, title)
    if published is None and body and meta is not None and meta.date:
        # htmldate's guess, worth something only on a page with an article.
        published = listing.parse_date(meta.date)
    return NewArticle(
        url=link.url,
        title=truncate(title, 500),
        summary=summary,
        content=body[:CONTENT_LIMIT] or None,
        author=(meta.author[:300] if meta and meta.author else None),
        tags=(),
        language=(
            language
            if language in {"ru", "en"}
            else detect_language(f"{title} {(body or summary)[:500]}")
        ),
        published_at=_not_ahead(published),
        content_hash=content_hash(title, body or summary),
        image_url=from_page(page, link.url),
        word_count=word_count(body or None),
    )


def published_on_page(page: str, title: str = "") -> datetime | None:
    """The moment the page says it was published: its meta tags, its JSON-LD,
    the first <time> with a machine-readable date, or a date in words next
    to the title ("18 мая 2026 г.", "May 18, 2026") on a page drawn by script."""
    tree = LexborHTMLParser(page[:2_000_000])
    for selector in (
        'meta[property="article:published_time"]',
        'meta[name="article:published_time"]',
        'meta[itemprop="datePublished"]',
        'meta[name="pubdate"]',
        'meta[name="date"]',
    ):
        node = tree.css_first(selector)
        if node is not None and (found := listing.parse_date(node.attributes.get("content") or "")):
            return found
    for script in tree.css('script[type="application/ld+json"]'):
        found = _ld_date(script.text())
        if found is not None:
            return found
    for node in tree.css("time[datetime]"):
        if found := listing.parse_date(node.attributes.get("datetime") or ""):
            return found
    for node in tree.css("script, style, noscript, template"):
        node.decompose()
    body = tree.body
    text = body.text(separator="\n", strip=True) if body is not None else ""
    # After the title: a list of other stories, with their dates, may come first.
    start = text.find(title[:40]) if title else -1
    return date_in_words(text[max(start, 0) :][:3000]) or date_in_words(text[:3000])


_MONTHS = {
    name: number
    for number, names in enumerate(
        (
            ("января", "january", "jan"),
            ("февраля", "february", "feb"),
            ("марта", "march", "mar"),
            ("апреля", "april", "apr"),
            ("мая", "may"),
            ("июня", "june", "jun"),
            ("июля", "july", "jul"),
            ("августа", "august", "aug"),
            ("сентября", "september", "sep", "sept"),
            ("октября", "october", "oct"),
            ("ноября", "november", "nov"),
            ("декабря", "december", "dec"),
        ),
        start=1,
    )
    for name in names
}
_DAY_MONTH_YEAR = re.compile(
    r"\b(\d{1,2})\s+([а-яёa-z]{3,9})\.?\s+((?:19|20)\d{2})\b", re.IGNORECASE
)
_MONTH_DAY_YEAR = re.compile(r"\b([a-z]{3,9})\.?\s+(\d{1,2}),?\s+((?:19|20)\d{2})\b", re.IGNORECASE)
_DOTTED = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.((?:19|20)\d{2})\b")


def date_in_words(text: str) -> datetime | None:
    """The first date written out in `text`, as midnight UTC of that day."""
    found: list[tuple[int, datetime]] = []
    for match in _DAY_MONTH_YEAR.finditer(text):
        month = _MONTHS.get(match[2].lower())
        if month and (day := _day(int(match[3]), month, int(match[1]))):
            found.append((match.start(), day))
            break
    for match in _MONTH_DAY_YEAR.finditer(text):
        month = _MONTHS.get(match[1].lower())
        if month and (day := _day(int(match[3]), month, int(match[2]))):
            found.append((match.start(), day))
            break
    for match in _DOTTED.finditer(text):
        if day := _day(int(match[3]), int(match[2]), int(match[1])):
            found.append((match.start(), day))
            break
    return min(found)[1] if found else None


def _day(year: int, month: int, day: int) -> datetime | None:
    try:
        return datetime(year, month, day, tzinfo=UTC)
    except ValueError:
        return None


def _ld_date(raw: str) -> datetime | None:
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    stack = [data]
    while stack:
        item = stack.pop()
        if isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, dict):
            stamp = item.get("datePublished")
            if isinstance(stamp, str) and (found := listing.parse_date(stamp)):
                return found
            stack.extend(value for value in item.values() if isinstance(value, dict | list))
    return None


def _not_ahead(moment: datetime | None) -> datetime:
    """A page with a wrong clock must not push an article outside every window."""
    now = datetime.now(UTC)
    if moment is None or moment > now + timedelta(hours=1):
        return now
    return moment
