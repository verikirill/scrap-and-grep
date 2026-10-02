"""A WordPress site through its REST API: posts with their whole text.

Many news sites run on WordPress, and some close the feed while leaving
the API open: CISOCLUB answers 403 on /feed/ to every client, Chrome
included, but /wp-json/wp/v2/posts gives the posts with their text, date
and address. A category (/category/news/) or a tag of the site becomes the
same request with its id. Only the fields used are asked for: a post with
everything an SEO plugin adds weighs a hundred kilobytes.
"""

import asyncio
import html
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode, urljoin, urlsplit

from radar.images.extract import first_img
from radar.ingest.feeds import CONTENT_LIMIT, MAX_URL_LENGTH, SUMMARY_LIMIT, FeedResult
from radar.ingest.fetch import Ladder
from radar.ingest.listing import parse_date
from radar.ingest.pages import MarkupChanged
from radar.reading import word_count
from radar.store.articles import NewArticle
from radar.text import canonical_url, content_hash, detect_language, strip_html, truncate

API_PATH = "/wp-json/wp/v2/"
PER_PAGE = 20
FIELDS = "id,link,title,date_gmt,content,excerpt"


def posts_url(site: str, *, category: int | None = None, tag: int | None = None) -> str:
    """The API address of a site's newest posts, of one category or tag if given."""
    parts = urlsplit(site)
    query: dict[str, str | int] = {"per_page": PER_PAGE, "_fields": FIELDS}
    if category is not None:
        query["categories"] = category
    if tag is not None:
        query["tags"] = tag
    return f"{parts.scheme}://{parts.netloc}{API_PATH}posts?{urlencode(query)}"


def terms_url(site: str, taxonomy: str, slug: str) -> str:
    """Where the API finds a category's or tag's id by its slug."""
    parts = urlsplit(site)
    query = urlencode({"slug": slug, "_fields": "id,name"})
    return f"{parts.scheme}://{parts.netloc}{API_PATH}{taxonomy}?{query}"


def is_posts_url(url: str) -> bool:
    return API_PATH + "posts" in urlsplit(url).path


async def fetch_posts(
    ladder: Ladder,
    url: str,
    *,
    language: str,
    etag: str | None,
    last_modified: str | None,
) -> FeedResult:
    headers = {"Accept": "application/json"}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    response = await ladder.get(url, headers=headers, expect="any")
    if response.status_code == 304:
        return FeedResult(status="not_modified", etag=etag, last_modified=last_modified)
    response.raise_for_status()
    try:
        posts = response.json()
    except ValueError as exc:
        raise MarkupChanged(f"{url} did not answer with JSON") from exc
    if not isinstance(posts, list):
        raise MarkupChanged(f"{url} did not answer with a list of posts")
    articles = await asyncio.to_thread(parse_posts, posts, url, language)
    if posts and not articles:
        raise MarkupChanged(f"none of the posts at {url} could be read")
    return FeedResult(
        status="ok",
        articles=articles,
        etag=response.headers.get("etag"),
        last_modified=response.headers.get("last-modified"),
    )


def parse_posts(posts: list[Any], base: str, language: str) -> tuple[NewArticle, ...]:
    now = datetime.now(UTC)
    found: dict[str, NewArticle] = {}
    for post in posts:
        article = _post(post, base, language, now)
        if article is not None and article.url not in found:
            found[article.url] = article
    return tuple(found.values())


def _rendered(post: dict[str, Any], key: str) -> str:
    value = post.get(key)
    if isinstance(value, dict):
        value = value.get("rendered")
    return value if isinstance(value, str) else ""


def _post(post: Any, base: str, language: str, now: datetime) -> NewArticle | None:
    if not isinstance(post, dict):
        return None
    link = urljoin(base, str(post.get("link") or ""))
    title = html.unescape(strip_html(_rendered(post, "title")))
    if not title or not link.startswith(("http://", "https://")) or len(link) > MAX_URL_LENGTH:
        return None
    markup = _rendered(post, "content")
    content = html.unescape(strip_html(markup)) or None
    summary = html.unescape(strip_html(_rendered(post, "excerpt")))
    stamp = post.get("date_gmt")
    published = parse_date(f"{stamp}+00:00") if isinstance(stamp, str) and stamp else None
    if published is None or published > now:
        published = now
    body = content or summary
    return NewArticle(
        url=canonical_url(link),
        title=truncate(title, 500),
        summary=truncate(summary, SUMMARY_LIMIT),
        content=content[:CONTENT_LIMIT] if content else None,
        author=None,
        tags=(),
        language=(
            language if language in {"ru", "en"} else detect_language(f"{title} {body[:500]}")
        ),
        published_at=published,
        content_hash=content_hash(title, body),
        image_url=first_img(markup, link),
        word_count=word_count(content),
    )
