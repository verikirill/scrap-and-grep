"""Protection bulletins of Symantec (Broadcom).

They are listed at broadcom.com/support/security-center/protection-bulletin,
a page drawn by script with no feed and no links in its markup. The script
takes the bulletins from /api/nocache/mblogs: a JSON object of years, each a
list of bulletins newest first, with the title, the day and the whole text.
Without `limit` the answer is every bulletin since 2020, 9 MB; `limit=20`
gives the twenty newest of each year, a quarter of a megabyte, of which the
twenty newest overall are taken.

A bulletin's own page is named in `url`; some have none, and are given the
list's address with their id, so that each one keeps an address of its own.
"""

import asyncio
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin

from radar.ingest.feeds import CONTENT_LIMIT, MAX_URL_LENGTH, SUMMARY_LIMIT, FeedResult
from radar.ingest.fetch import Ladder
from radar.ingest.pages import MarkupChanged
from radar.reading import word_count
from radar.store.articles import NewArticle
from radar.text import canonical_url, content_hash, strip_html, truncate

SITE = "https://www.broadcom.com"
LISTING = f"{SITE}/support/security-center/protection-bulletin"
API = f"{SITE}/api/nocache/mblogs?locale=en-us&limit=20"
NEWEST = 20
MAX_BYTES = 3_000_000
TAG = "Symantec Protection Bulletin"
HIGHLIGHT_TAG = "Protection Highlight"
_MONTHS = {
    name: number
    for number, name in enumerate(
        (
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ),
        start=1,
    )
}
# "December 31, 2020"
_DATE_RE = re.compile(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})")


def parse_bulletins(answer: Any, now: datetime) -> tuple[NewArticle, ...]:
    if not isinstance(answer, dict):
        raise MarkupChanged("the bulletins did not come as an object of years")
    items = [item for year in answer.values() if isinstance(year, list) for item in year]
    found: dict[str, NewArticle] = {}
    for item in items:
        article = _bulletin(item, now)
        if article is not None and article.url not in found:
            found[article.url] = article
    if items and not found:
        raise MarkupChanged(f"none of {len(items)} bulletins could be read")
    newest = sorted(found.values(), key=lambda article: article.published_at, reverse=True)
    return tuple(newest[:NEWEST])


def _bulletin(item: Any, now: datetime) -> NewArticle | None:
    if not isinstance(item, dict):
        return None
    title = " ".join(strip_html(str(item.get("title") or "")).split())
    published = _day(str(item.get("published") or ""))
    if not title or published is None:
        return None
    content = strip_html(str(item.get("body") or "")) or None
    link = item.get("url")
    url = (
        urljoin(SITE, link)
        if isinstance(link, str) and link.startswith("/")
        else f"{LISTING}?id={item.get('content_id') or ''}"
    )
    if len(url) > MAX_URL_LENGTH:
        return None
    highlight = str(item.get("highlight") or "").lower() == "yes"
    return NewArticle(
        url=canonical_url(url),
        title=truncate(title, 500),
        summary=truncate(content or title, SUMMARY_LIMIT),
        content=content[:CONTENT_LIMIT] if content else None,
        author=None,
        tags=(TAG, HIGHLIGHT_TAG) if highlight else (TAG,),
        language="en",
        published_at=min(published, now),
        content_hash=content_hash(title, content or ""),
        word_count=word_count(content),
    )


def _day(text: str) -> datetime | None:
    match = _DATE_RE.search(text)
    if match is None or (month := _MONTHS.get(match.group(1).lower())) is None:
        return None
    try:
        return datetime(int(match.group(3)), month, int(match.group(2)), tzinfo=UTC)
    except ValueError:
        return None


async def fetch_bulletins(
    ladder: Ladder, url: str, *, etag: str | None, last_modified: str | None
) -> FeedResult:
    headers = {"Accept": "application/json"}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    response = await ladder.get(url, headers=headers, max_bytes=MAX_BYTES, expect="any")
    if response.status_code == 304:
        return FeedResult(status="not_modified", etag=etag, last_modified=last_modified)
    response.raise_for_status()
    try:
        answer = response.json()
    except ValueError as exc:
        raise MarkupChanged(f"{url} did not answer with JSON") from exc
    articles = await asyncio.to_thread(parse_bulletins, answer, datetime.now(UTC))
    return FeedResult(
        status="ok",
        articles=articles,
        etag=response.headers.get("etag"),
        last_modified=response.headers.get("last-modified"),
    )
