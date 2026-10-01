"""Fetch a feed with a conditional GET and turn its entries into articles."""

import asyncio
import calendar
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import feedparser
import httpx

from radar.images.extract import from_entry
from radar.ingest.net import safe_get
from radar.store.articles import NewArticle
from radar.text import canonical_url, content_hash, detect_language, strip_html, truncate

SUMMARY_LIMIT = 1500
LONG_SUMMARY = 1800
CONTENT_LIMIT = 40_000
MAX_URL_LENGTH = 2000
MAX_TAGS = 12


@dataclass(frozen=True, slots=True)
class FeedResult:
    status: Literal["ok", "not_modified"]
    articles: tuple[NewArticle, ...] = ()
    etag: str | None = None
    last_modified: str | None = None


async def fetch_feed(
    client: httpx.AsyncClient,
    feed_url: str,
    *,
    language: str,
    etag: str | None,
    last_modified: str | None,
) -> FeedResult:
    headers = {}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    response = await safe_get(client, feed_url, headers=headers)
    if response.status_code == 304:
        return FeedResult(status="not_modified", etag=etag, last_modified=last_modified)
    response.raise_for_status()
    # feedparser is synchronous and CPU-bound; keep it off the event loop.
    parsed = await asyncio.to_thread(feedparser.parse, response.content)
    if parsed.bozo and not parsed.entries:
        raise ValueError(f"not a feed: {parsed.bozo_exception}")
    return FeedResult(
        status="ok",
        articles=parse_entries(parsed.entries, language),
        etag=response.headers.get("etag"),
        last_modified=response.headers.get("last-modified"),
    )


def parse_entries(entries: list[Any], language: str) -> tuple[NewArticle, ...]:
    now = datetime.now(UTC)
    seen: set[str] = set()
    articles = []
    for entry in entries:
        article = _parse_entry(entry, language, now)
        if article is None or article.url in seen:
            continue
        seen.add(article.url)
        articles.append(article)
    return tuple(articles)


def _parse_entry(entry: Any, language: str, now: datetime) -> NewArticle | None:
    title = strip_html(entry.get("title", ""))
    link = entry.get("link", "")
    if not title or not link.startswith(("http://", "https://")) or len(link) > MAX_URL_LENGTH:
        return None

    summary = strip_html(entry.get("summary", ""))
    content = None
    if entry.get("content"):
        content = strip_html(" ".join(part.get("value", "") for part in entry["content"])) or None
    if content is None and len(summary) > LONG_SUMMARY:
        # Some feeds (CISA advisories, for one) put the whole text in <description>.
        content = summary
    tags = tuple(
        dict.fromkeys(
            tag["term"].strip()
            for tag in entry.get("tags", [])
            if isinstance(tag.get("term"), str) and tag["term"].strip()
        )
    )[:MAX_TAGS]
    body = content or summary
    return NewArticle(
        url=canonical_url(link),
        title=truncate(title, 500),
        summary=truncate(summary, SUMMARY_LIMIT),
        content=content[:CONTENT_LIMIT] if content else None,
        author=(entry.get("author") or None) and str(entry["author"])[:300],
        tags=tags,
        language=language if language in {"ru", "en"} else detect_language(f"{title} {body[:500]}"),
        published_at=_published_at(entry, now),
        content_hash=content_hash(title, body),
        image_url=from_entry(entry, link),
    )


def _published_at(entry: Any, now: datetime) -> datetime:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed is None:
        return now
    published = datetime.fromtimestamp(calendar.timegm(parsed), tz=UTC)
    # A feed with a wrong clock must not push an article outside every window.
    if published > now + timedelta(hours=1):
        return now
    return published
