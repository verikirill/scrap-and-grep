"""What an address is, and how to read it: any address a reader pastes.

In turn:
1. "@name" or a t.me address is a Telegram channel;
2. an address that answers with RSS or Atom is a feed;
3. a page that names its feed (<link rel="alternate">) or has one at a usual
   path (/feed, /rss, /rss.xml, /atom.xml) is read through that feed;
4. a WordPress site whose feed is closed is read through its REST API, the
   page's category or tag kept;
5. otherwise the page is a news section whose links lead to the articles
   (ingest/listing.py), or, failing that, the site's sitemap is.

The answer names the kind, the step of the ladder that read the page and
the newest articles found, before anything is saved. It runs in the ingest
worker, where the browser is: a list drawn by script shows its articles too.
"""

import asyncio
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urljoin, urlsplit

import feedparser
import httpx
from selectolax.lexbor import LexborHTMLParser

from radar.db.models import Source
from radar.ingest import listing, telegram, wordpress
from radar.ingest.feeds import parse_entries
from radar.ingest.fetch import LIGHT, Blocked, Ladder, Outcome
from radar.ingest.net import UnresolvableHostError, UnsafeUrlError
from radar.ingest.pages import MarkupChanged
from radar.logging import get_logger
from radar.store.articles import NewArticle
from radar.text import detect_language, stable_hash, untracked_url

log = get_logger(__name__)

SAMPLES = 3
# How long the worker's answer waits for the api to take it.
DETECT_TTL_SECONDS = 600
# Where sites usually keep a feed, tried when the page names none.
FEED_PATHS = ("feed/", "/feed", "/rss", "/rss.xml", "/atom.xml", "/feed.xml")
SITEMAP_PATHS = ("/news-sitemap.xml", "/sitemap_news.xml", "/sitemap.xml")
_WP_TERM = re.compile(r"/(category|tag)/([^/?#]+)/?$")
_FEED_TYPES = ("application/rss+xml", "application/atom+xml", "application/feed+json")


class NotFound(Exception):
    """Nothing readable at the address; the message is for the reader."""


@dataclass(frozen=True, slots=True)
class Sample:
    title: str
    url: str
    published_at: datetime | None = None


@dataclass(slots=True)
class Found:
    kind: str
    # The feed, API or page address to poll; a channel's name for Telegram.
    address: str
    name: str
    site_url: str | None
    language: str
    samples: list[Sample] = field(default_factory=list)
    link_selector: str | None = None
    # How the address was read: the step of the ladder, and why not lower.
    fetch_method: str | None = None
    fetch_note: str | None = None


async def detect(address: str, client: httpx.AsyncClient, selector: str | None = None) -> Found:
    address = address.strip()
    if _is_channel(address):
        return await _channel(address, client)
    url = address if "://" in address else f"https://{address}"
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise NotFound("Не похоже на корректный адрес сайта или Telegram-канала.")
    async with Ladder(client) as ladder, Ladder(client, steps=LIGHT) as light:
        try:
            response = await ladder.get(url, expect="any")
        except UnresolvableHostError as exc:
            raise NotFound("Сайт не найден: доменное имя отсутствует в DNS.") from exc
        except UnsafeUrlError as exc:
            raise NotFound(
                "Адрес ведёт во внутреннюю сеть: добавление таких источников запрещено."
            ) from exc
        except Blocked as exc:
            raise NotFound(f"Не удалось загрузить страницу ни одним из способов: {exc}") from exc
        except httpx.HTTPError as exc:
            raise NotFound(f"Сайт не ответил ({type(exc).__name__}).") from exc
        if response.status_code >= 400:
            raise NotFound(f"Сайт ответил {response.status_code}.")
        final = str(response.request.url)
        found = _as_feed(final, response) if not selector else None
        if found is None and not selector and _is_html(response):
            found = await _named_feed(light, final, response.text)
            if found is None and _looks_like_wordpress(response.text):
                found = await _wordpress(light, final)
        if found is None:
            found = await _page(ladder, url, response, selector)
        if found is None and not selector:
            found = await _sitemap(light, final)
        if found is None:
            raise NotFound(
                "На странице нет ленты новостей или ссылок на статьи. "
                "Укажите CSS-селектор ссылок или адрес новостного раздела."
            )
        if found.fetch_method is None:
            _note(found, ladder.first)
        if not found.name:
            found.name = _page_name(response.text, final) if _is_html(response) else parts.hostname
        found.language = _language([sample.title for sample in found.samples])
        return found


def as_source(found: Found, category: str = "security") -> Source:
    """The catalog's row for what an address turned out to be, as the form in
    «Источники» adds it: a channel by its name, anything else by the address
    it is polled at."""
    name = found.name.strip()[:200] or found.address[:200]
    language = "en" if found.language == "en" else "ru"
    if found.kind == "telegram":
        return Source(
            slug=f"tg-{found.address}",
            name=name,
            kind="telegram",
            feed_url=telegram.feed_url(found.address),
            site_url=telegram.site_url(found.address),
            category=category,
            language=language,
            # A channel's short posts mostly point to articles worth opening.
            fetch_full_text=True,
        )
    return Source(
        slug=f"custom-{stable_hash(found.address)[:12]}",
        name=name,
        kind=found.kind,
        link_selector=found.link_selector,
        feed_url=found.address,
        site_url=found.site_url,
        category=category,
        language=language,
        fetch_full_text=False,
    )


def detect_key(request_id: str) -> str:
    return f"detect:{request_id}"


def detected_json(found: Found) -> dict[str, object]:
    """The answer as the api passes it on: dates as ISO strings."""
    return {
        "kind": found.kind,
        "address": found.address,
        "name": found.name,
        "site_url": found.site_url,
        "language": found.language,
        "link_selector": found.link_selector,
        "fetch_method": found.fetch_method,
        "fetch_note": found.fetch_note,
        "samples": [
            {
                "title": sample.title,
                "url": sample.url,
                "published_at": sample.published_at.isoformat() if sample.published_at else None,
            }
            for sample in found.samples
        ],
    }


def _is_channel(address: str) -> bool:
    if address.startswith("@"):
        return True
    host = urlsplit(address if "://" in address else f"https://{address}").hostname or ""
    return host in {"t.me", "telegram.me"}


async def _channel(address: str, client: httpx.AsyncClient) -> Found:
    try:
        name = telegram.parse_channel(address)
        title = await telegram.channel_title(client, name)
        feed = await telegram.fetch_channel(
            client, telegram.feed_url(name), language="ru", last_post_id=None
        )
    except ValueError as exc:
        raise NotFound(str(exc)) from exc
    except telegram.ChannelUnavailable as exc:
        raise NotFound("Канал не найден или закрыл веб-превью.") from exc
    except (httpx.HTTPError, MarkupChanged, OSError) as exc:
        raise NotFound("Сервис t.me не ответил либо на странице нет постов канала.") from exc
    newest = sorted(feed.articles, key=lambda item: item.published_at, reverse=True)
    return Found(
        kind="telegram",
        address=name,
        name=title if len(title) >= 2 else f"@{name}",
        site_url=telegram.site_url(name),
        language="ru",
        samples=_samples(newest[:SAMPLES]),
        fetch_method="plain",
    )


def _is_html(response: httpx.Response) -> bool:
    kind = response.headers.get("content-type", "")
    head = response.content[:2000].lstrip().lower()
    return "html" in kind or head.startswith((b"<!doctype html", b"<html"))


def _as_feed(url: str, response: httpx.Response) -> Found | None:
    """The address is itself a feed: RSS, Atom or RDF with entries."""
    head = response.content[:20_000].lower()
    if not any(tag in head for tag in (b"<rss", b"<feed", b"<rdf:rdf")):
        return None
    parsed = feedparser.parse(response.content)
    if not parsed.entries:
        return None
    articles = sorted(
        parse_entries(parsed.entries, "auto"), key=lambda item: item.published_at, reverse=True
    )
    link = parsed.feed.get("link") if isinstance(parsed.feed.get("link"), str) else None
    return Found(
        kind="rss",
        address=url,
        name=str(parsed.feed.get("title") or "").strip()[:200],
        site_url=link,
        language="ru",
        samples=_samples(articles[:SAMPLES]),
    )


async def _named_feed(ladder: Ladder, url: str, page: str) -> Found | None:
    """The feed the page names, or one at a usual path."""
    tree = LexborHTMLParser(page)
    named = [
        urljoin(url, node.attributes.get("href") or "")
        for node in tree.css('link[rel="alternate"]')
        if (node.attributes.get("type") or "").lower() in _FEED_TYPES
        and node.attributes.get("href")
        # Comment feeds say nothing new.
        and "comments" not in (node.attributes.get("href") or "")
    ]
    # The page's own section first: a category's feed rather than the site's.
    named.sort(key=lambda feed: not feed.startswith(url.rstrip("/")))
    candidates = list(dict.fromkeys([*named, *(urljoin(url, path) for path in FEED_PATHS)]))
    for candidate in candidates[:8]:
        try:
            response = await ladder.get(candidate, expect="feed")
        except httpx.HTTPError, UnsafeUrlError:
            continue
        if response.status_code >= 400:
            continue
        found = _as_feed(candidate, response)
        if found is not None:
            found.site_url = found.site_url or url
            return found
    return None


def _looks_like_wordpress(page: str) -> bool:
    lowered = page[:500_000].lower()
    return "/wp-content/" in lowered or "api.w.org" in lowered or "/wp-json/" in lowered


async def _wordpress(ladder: Ladder, url: str) -> Found | None:
    """The REST API of a WordPress site, the page's category or tag kept."""
    category = tag = None
    term = _WP_TERM.search(urlsplit(url).path)
    if term is not None:
        taxonomy = "categories" if term[1] == "category" else "tags"
        try:
            answer = await ladder.get(wordpress.terms_url(url, taxonomy, term[2]), expect="any")
            terms = answer.json() if answer.status_code == 200 else []
        except httpx.HTTPError, UnsafeUrlError, ValueError:
            terms = []
        if isinstance(terms, list) and terms and isinstance(terms[0], dict):
            if taxonomy == "categories":
                category = terms[0].get("id")
            else:
                tag = terms[0].get("id")
    api = wordpress.posts_url(url, category=category, tag=tag)
    try:
        feed = await wordpress.fetch_posts(
            ladder, api, language="auto", etag=None, last_modified=None
        )
    except (httpx.HTTPError, UnsafeUrlError, MarkupChanged) as exc:
        log.info("detect_wordpress_failed", url=url, error=type(exc).__name__)
        return None
    if not feed.articles:
        return None
    found = Found(
        kind="wordpress",
        address=api,
        name="",
        site_url=url,
        language="ru",
        samples=_samples(feed.articles[:SAMPLES]),
    )
    return found


async def _page(
    ladder: Ladder, url: str, response: httpx.Response, selector: str | None
) -> Found | None:
    """The page as a news section, read up the ladder if its list is drawn by script."""
    links = await asyncio.to_thread(listing.find_links, response.text, url, selector)
    if not links:
        try:
            again = await ladder.get(
                url,
                expect="page",
                wanted=lambda page: bool(listing.find_links(page.text, url, selector)),
            )
        except httpx.HTTPError, UnsafeUrlError:
            return None
        links = await asyncio.to_thread(listing.find_links, again.text, url, selector)
    if not links:
        return None
    return Found(
        kind="page",
        address=untracked_url(url),
        name="",
        site_url=untracked_url(url),
        language="ru",
        samples=_samples(links[:SAMPLES]),
        link_selector=selector,
    )


async def _sitemap(ladder: Ladder, url: str) -> Found | None:
    """The site's sitemap, when its page lists no articles: a news one first."""
    root = f"{urlsplit(url).scheme}://{urlsplit(url).netloc}"
    for path in SITEMAP_PATHS:
        candidate = root + path
        try:
            response = await ladder.get(candidate, expect="any")
        except httpx.HTTPError, UnsafeUrlError:
            continue
        if response.status_code >= 400 or not listing.is_sitemap(response.text):
            continue
        body, address = response.text, candidate
        if "<sitemapindex" in body[:3000].lower():
            children = listing.sitemap_children(body, candidate)
            if not children:
                continue
            try:
                child = await ladder.get(children[0], expect="any")
            except httpx.HTTPError, UnsafeUrlError:
                continue
            body = child.text
        links = listing.sitemap_links(body, url)
        if len(links) >= listing.MIN_LINKS:
            return Found(
                kind="page",
                address=address,
                name="",
                site_url=url,
                language="ru",
                samples=_samples(links[:SAMPLES]),
            )
    return None


def _samples(items: Sequence[NewArticle | listing.Link]) -> list[Sample]:
    return [Sample(item.title, item.url, item.published_at) for item in items]


def _note(found: Found, outcome: Outcome | None) -> None:
    if outcome is not None and outcome.step:
        found.fetch_method = outcome.step
        found.fetch_note = outcome.note


def _page_name(page: str, url: str) -> str:
    tree = LexborHTMLParser(page[:500_000])
    for selector in ('meta[property="og:site_name"]', 'meta[name="application-name"]'):
        node = tree.css_first(selector)
        if node is not None and (name := (node.attributes.get("content") or "").strip()):
            return name[:200]
    title = tree.css_first("title")
    text = " ".join(title.text().split()) if title is not None else ""
    return (text or urlsplit(url).hostname or url)[:200]


def _language(titles: list[str]) -> str:
    text = " ".join(titles)
    return detect_language(text) if text.strip() else "ru"
