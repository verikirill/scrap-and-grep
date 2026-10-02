"""Trending vulnerabilities of Positive Technologies.

They are listed at ptsecurity.com/research/trending-vulnerabilities/.

PT calls a vulnerability trending when it is already exploited or about to
be, and has to be fixed or covered at once. The page lists them newest first,
ten to a page, each with a rating, a CVSS vector, the vendor, the product and
the day it became trending. There is no feed, so the first page is read;
a vulnerability becomes an article on the day PT marked it.

The page is built by Next.js, and its class names change with every release.
Cards are found by what does not change: the rating block's data-testid, the
heading with the identifier, and the "label: value" pairs.
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from itertools import pairwise
from urllib.parse import quote, urljoin, urlsplit

from selectolax.lexbor import LexborHTMLParser, LexborNode

from radar.ingest.feeds import MAX_URL_LENGTH, SUMMARY_LIMIT, FeedResult
from radar.ingest.fetch import Ladder
from radar.ingest.pages import MarkupChanged
from radar.reading import word_count
from radar.store.articles import NewArticle
from radar.text import canonical_url, content_hash, truncate

PAGE_MAX_BYTES = 3_000_000
# "CVE-2026-85102", "BDU:2026-01331"; a longer heading is not an identifier.
MAX_ID = 64
MOSCOW = timezone(timedelta(hours=3))
TAG = "трендовая уязвимость"
_MONTHS = {
    name: number
    for number, name in enumerate(
        (
            "января",
            "февраля",
            "марта",
            "апреля",
            "мая",
            "июня",
            "июля",
            "августа",
            "сентября",
            "октября",
            "ноября",
            "декабря",
        ),
        start=1,
    )
}
_DATE_RE = re.compile(r"(\d{1,2})\s+([а-яё]+)\s+(\d{4})", re.IGNORECASE)
# The dash between the rating and the score has spaces round it; a hyphen
# inside a word ("Средне-высокий") does not.
_DASH_RE = re.compile(r"\s+[–—-]\s+")
_SCORE_RE = re.compile(r"\d{1,2}(?:[.,]\d)?")


@dataclass(frozen=True, slots=True)
class Trending:
    id: str
    url: str
    description: str
    rating: str
    score: str | None
    vector: str
    vendor: str
    product: str
    since: date

    @property
    def software(self) -> str:
        """The vendor and the product, without saying the vendor twice.

        "Check Point Quantum Security Gateway", but "Microsoft Windows" for
        Microsoft and Microsoft Windows.
        """
        if not self.product:
            return self.vendor
        if not self.vendor or self.vendor.lower() in self.product.lower():
            return self.product
        return f"{self.vendor} {self.product}"


def parse_trending(page: str, base: str) -> tuple[Trending, ...]:
    tree = LexborHTMLParser(page)
    blocks = tree.css('[data-testid="research-rating-and-code"]')
    found = [item for block in blocks if (item := _card(block, base)) is not None]
    if blocks and not found:
        raise MarkupChanged(f"не прочитана ни одна из {len(blocks)} карточек")
    if not blocks and tree.css_first("h1") is None:
        raise MarkupChanged("на странице нет ни карточек, ни заголовка")
    return tuple(found)


def _card(rating: LexborNode, base: str) -> Trending | None:
    card = rating.parent
    while card is not None and card.tag != "article":
        card = card.parent
    if card is None:
        return None
    heading, text, link = card.css_first("h3"), card.css_first("p"), card.css_first("a[href]")
    fields = _fields(card)
    since = _day(fields.get("Стала трендовой", ""))
    if heading is None or text is None or since is None:
        return None
    ident = " ".join(heading.text().split())
    if not ident or len(ident) > MAX_ID:
        return None
    href = (link.attributes.get("href") or "") if link else ""
    badge = [" ".join(small.text().split()) for small in rating.css("small")]
    # "Критический – 9.8", or "Без рейтинга" with no score.
    label, *score = _DASH_RE.split(badge[0] if badge else "", maxsplit=1)
    return Trending(
        id=ident,
        url=_card_url(base, href, ident),
        description=" ".join(text.text().split()),
        rating=label.strip(),
        score=(
            match.group(0).replace(",", ".")
            if score and (match := _SCORE_RE.search(score[0]))
            else None
        ),
        vector=badge[1] if len(badge) > 1 else "",
        vendor=fields.get("Вендор", ""),
        product=fields.get("Уязвимый продукт", ""),
        since=since,
    )


def _card_url(base: str, href: str, ident: str) -> str:
    """The card's own page on PT's site.

    The card links to it relative to the list ("CVE-2026-85102"). A link to
    another site or of another scheme is not taken: the address becomes the
    article's, and two cards must never share one.
    """
    folder = base if base.endswith("/") else f"{base}/"
    host = urlsplit(folder).hostname
    for candidate in (
        urljoin(folder, href) if href else "",
        # "./" keeps "BDU:2026-1" from reading as a scheme.
        urljoin(folder, "./" + quote(ident, safe=":-.")),
    ):
        parts = urlsplit(candidate)
        if (
            parts.scheme in {"http", "https"}
            and parts.hostname == host
            and parts.path.rstrip("/").endswith(quote(ident, safe=":-."))
            and len(candidate) <= MAX_URL_LENGTH
        ):
            return candidate
    return urljoin(folder, "./" + quote(ident, safe=""))


def _fields(card: LexborNode) -> dict[str, str]:
    """The "Вендор: Check Point" pairs: a label ending with a colon, then its value."""
    texts = [" ".join(small.text().split()) for small in card.css("small")]
    return {
        label[:-1].strip(): value
        for label, value in pairwise(texts)
        if label.endswith(":") and not value.endswith(":")
    }


def _day(text: str) -> date | None:
    match = _DATE_RE.search(text)
    if match is None or (month := _MONTHS.get(match.group(2).lower())) is None:
        return None
    try:
        return date(int(match.group(3)), month, int(match.group(1)))
    except ValueError:
        return None


def to_article(item: Trending, now: datetime) -> NewArticle:
    title = f"Трендовая уязвимость {item.id} в {item.software}" if item.software else item.id
    danger = ", ".join(
        part for part in (item.rating, f"CVSS {item.score}" if item.score else "") if part
    )
    lines = [
        item.description,
        f"Уровень опасности: {danger}." if danger else "",
        f"Вектор CVSS: {item.vector}." if item.vector else "",
        f"Вендор: {item.vendor}. Продукт: {item.product}." if item.vendor else "",
        f"Positive Technologies отнесла уязвимость к трендовым {item.since:%d.%m.%Y}.",
    ]
    content = "\n".join(line for line in lines if line)
    published = datetime.combine(item.since, time(), tzinfo=MOSCOW).astimezone(UTC)
    return NewArticle(
        url=canonical_url(item.url),
        title=title,
        summary=truncate(item.description, SUMMARY_LIMIT),
        content=content,
        author=None,
        tags=tuple(dict.fromkeys(tag for tag in (TAG, item.id, item.vendor) if tag)),
        language="ru",
        published_at=min(published, now),
        content_hash=content_hash(title, content),
        word_count=word_count(content),
    )


async def fetch_trending(
    ladder: Ladder, url: str, *, etag: str | None, last_modified: str | None
) -> FeedResult:
    headers = {}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    response = await ladder.get(url, headers=headers, max_bytes=PAGE_MAX_BYTES, expect="page")
    if response.status_code == 304:
        return FeedResult(status="not_modified", etag=etag, last_modified=last_modified)
    response.raise_for_status()
    now = datetime.now(UTC)
    items = parse_trending(response.text, str(response.request.url))
    articles = {article.url: article for article in (to_article(item, now) for item in items)}
    return FeedResult(
        status="ok",
        articles=tuple(articles.values()),
        etag=response.headers.get("etag"),
        last_modified=response.headers.get("last-modified"),
    )
