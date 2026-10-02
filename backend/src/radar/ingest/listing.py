"""Articles of a site without a feed: links found on its news page.

A news section lists its articles in blocks of one markup, a card or a row
repeated down the page, each with a link to the article. Navigation, tags,
pagination and links to other sites are repeated too, but look different:
their addresses are short, shared by many pages or lead elsewhere. So the
links of the page are grouped by where they sit in the markup (the tags and
classes of their ancestors), each group is scored by how much its links
look like articles, and the best groups are taken in page order.

An address looks like an article when it has a date in its path, a slug of
several words, or a long number, and is not one of the kinds of pages every
site has (tags, authors, search, the next page). A hash route of a page
drawn by script ("#/news/<id>") counts as a path.

When the markup is unusual, a CSS selector of the links, set on the source,
is used instead. A sitemap (urlset or news sitemap) is read as a listing too.
"""

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit

from selectolax.lexbor import LexborHTMLParser, LexborNode

from radar.text import canonical_url, untracked_url

# Most a listing gives per run; a news page shows 10 to 50.
MAX_LINKS = 60
# A group of links in one markup is taken from this many on.
MIN_GROUP = 3
# Fewer than this, and the page is not taken for a listing at all.
MIN_LINKS = 3
_SIGNATURE_DEPTH = 4
_MIN_TITLE_CHARS = 12
_NOT_ARTICLES = re.compile(
    r"/(tags?|tegi|category|categories|rubric|rubrics|section|topics?|author|authors|avtor|"
    r"page|pages|search|login|signin|signup|register|account|profile|cart|subscribe|"
    r"about|contacts?|privacy|terms|cookies?|policy|feed|rss|amp|wp-content|wp-admin|"
    r"wp-json|cdn-cgi|static|assets|media|uploads|files|events?|jobs|careers|vacancies)(/|$)",
    re.IGNORECASE,
)
_FILE = re.compile(
    r"\.(pdf|jpe?g|png|gif|webp|svg|zip|rar|7z|docx?|xlsx?|pptx?|mp4|mp3|xml|json|ics)$",
    re.IGNORECASE,
)
_DATE_IN_PATH = re.compile(r"/(19|20)\d{2}[/-](0?[1-9]|1[0-2])([/-]|$)|/(19|20)\d{6}([/-]|$)")
_LONG_NUMBER = re.compile(r"\d{4,}")
_PAGINATION = re.compile(r"[?&](page|p|paged|start|offset)=\d+", re.IGNORECASE)
_SITEMAP_TAGS = ("<urlset", "<sitemapindex")


@dataclass(frozen=True, slots=True)
class Link:
    # The address as the site gives it, less tracking: some sites answer 404
    # to the canonical form without the trailing slash.
    url: str
    title: str
    # A date the listing shows next to the link, when it has one.
    published_at: datetime | None = None


def is_sitemap(body: str) -> bool:
    head = body[:3000].lower()
    return any(tag in head for tag in _SITEMAP_TAGS)


def find_links(page: str, base_url: str, selector: str | None = None) -> list[Link]:
    """The article links of a news page, in page order."""
    if is_sitemap(page):
        return sitemap_links(page, base_url)
    tree = LexborHTMLParser(page)
    for node in tree.css("script, style, noscript, template, svg"):
        node.decompose()
    if selector:
        anchors = _selected(tree, selector)
        return _dedupe(
            [link for anchor in anchors if (link := _link(anchor, base_url, strict=False))]
        )
    groups: dict[tuple[str, ...], list[tuple[int, Link]]] = defaultdict(list)
    for position, anchor in enumerate(tree.css("a[href]")):
        link = _link(anchor, base_url, strict=True)
        if link is not None:
            groups[_signature(anchor)].append((position, link))
    scored = []
    for members in groups.values():
        distinct = {link.url: link for _, link in members}
        if len(distinct) >= MIN_GROUP:
            mean = sum(_score(link, base_url) for link in distinct.values()) / len(distinct)
            scored.append((mean, members))
    if not scored:
        return []
    # The articles are the group that looks most like them; a page may show
    # them in more than one markup (a lead story, then the rest), so groups
    # nearly as good are taken too. Menus and tag clouds score lower.
    best = max(mean for mean, _ in scored)
    chosen = [item for mean, members in scored if mean >= best * 0.8 for item in members]
    chosen.sort(key=lambda item: item[0])
    links = _dedupe([link for _, link in chosen])
    return links if len(links) >= MIN_LINKS else []


def sitemap_links(body: str, base_url: str) -> list[Link]:
    """Pages of a sitemap, newest first; a news sitemap gives titles too."""
    tree = LexborHTMLParser(body)
    links = []
    for entry in tree.css("url"):
        location = entry.css_first("loc")
        if location is None:
            continue
        url = urljoin(base_url, location.text(strip=True))
        if not _looks_like_article(url, base_url):
            continue
        title_node = entry.css_first("news\\:title")
        stamp_node = entry.css_first("news\\:publication_date") or entry.css_first("lastmod")
        links.append(
            Link(
                url=untracked_url(url),
                title=title_node.text(strip=True) if title_node is not None else "",
                published_at=parse_date(stamp_node.text(strip=True)) if stamp_node else None,
            )
        )
    epoch = datetime.min.replace(tzinfo=UTC)
    links.sort(key=lambda link: link.published_at or epoch, reverse=True)
    return _dedupe(links)


def sitemap_children(body: str, base_url: str) -> list[str]:
    """The sitemaps a sitemap index lists, newest and news ones first."""
    tree = LexborHTMLParser(body)
    found = []
    for entry in tree.css("sitemap"):
        location = entry.css_first("loc")
        if location is None:
            continue
        stamp = entry.css_first("lastmod")
        found.append(
            (
                "news" in location.text().lower(),
                parse_date(stamp.text(strip=True)) if stamp else None,
                urljoin(base_url, location.text(strip=True)),
            )
        )
    epoch = datetime.min.replace(tzinfo=UTC)
    found.sort(key=lambda item: (item[0], item[1] or epoch), reverse=True)
    return [url for _, _, url in found]


def _selected(tree: LexborHTMLParser, selector: str) -> list[LexborNode]:
    anchors = []
    for node in tree.css(selector):
        if node.tag == "a":
            anchors.append(node)
        else:
            anchors.extend(node.css("a[href]"))
    return anchors


def _signature(anchor: LexborNode) -> tuple[str, ...]:
    """Where the link sits: the tags and first classes of its ancestors."""
    parts = []
    node: LexborNode | None = anchor
    for _ in range(_SIGNATURE_DEPTH):
        if node is None or node.tag in {"body", "html", None}:
            break
        classes = (node.attributes.get("class") or "").split()
        # Classes with numbers are often per item ("post-123"), not per kind.
        kept = sorted(name for name in classes if not any(ch.isdigit() for ch in name))[:2]
        parts.append(f"{node.tag}.{'.'.join(kept)}")
        node = node.parent
    return tuple(parts)


def _link(anchor: LexborNode, base_url: str, *, strict: bool) -> Link | None:
    href = (anchor.attributes.get("href") or "").strip()
    if not href or href.startswith(("mailto:", "tel:", "javascript:")):
        return None
    if href.startswith("#") and not href.startswith(("#/", "#!")):
        return None
    url = urljoin(base_url, href)
    if strict and not _looks_like_article(url, base_url):
        return None
    if not strict and urlsplit(url).scheme not in {"http", "https"}:
        return None
    title = _title(anchor)
    if strict and len(title) < _MIN_TITLE_CHARS:
        return None
    return Link(url=untracked_url(url), title=title, published_at=_date_near(anchor))


def _route(url: str) -> tuple[str, str]:
    """The path and query of the page, or of the hash route of a page drawn
    by script ("#/news/1?tab=2")."""
    parts = urlsplit(url)
    if parts.fragment.startswith(("/", "!")):
        path, _, query = parts.fragment.lstrip("!").partition("?")
        return path, query
    return parts.path, parts.query


def _own_part(path: str, base_path: str) -> list[str]:
    """The segments of `path` below the listing's own: /about/news/x under
    /about/news/ is x. The section's name says nothing of its articles."""
    segments = [segment for segment in path.split("/") if segment]
    for segment in (segment for segment in base_path.split("/") if segment):
        if not segments or segments[0] != segment:
            break
        segments.pop(0)
    return segments


def _score(link: Link, base_url: str) -> float:
    """How much a link looks like an article rather than a menu item."""
    path, _ = _route(link.url)
    base_path, _ = _route(base_url)
    own = _own_part(path, base_path)
    last = own[-1] if own else ""
    score = 0.0
    if _DATE_IN_PATH.search(path):
        score += 2
    if _LONG_NUMBER.search(last):
        score += 1
    if len(re.split(r"[-_]+", last)) >= 4:
        score += 1
    if len(link.title) >= 25:
        score += 1
    if len(link.title.split()) >= 4:
        score += 1
    if base_path.strip("/") and path.startswith(base_path.rstrip("/") + "/"):
        # Below the news page itself.
        score += 1
    return score


def _same_site(host: str, base_host: str) -> bool:
    one, two = host.lower().removeprefix("www."), base_host.lower().removeprefix("www.")
    return one == two or one.endswith(f".{two}") or two.endswith(f".{one}")


def _looks_like_article(url: str, base_url: str) -> bool:
    parts, base = urlsplit(url), urlsplit(base_url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return False
    if not _same_site(parts.hostname, base.hostname or ""):
        return False
    path, query = _route(url)
    if _FILE.search(path) or _PAGINATION.search(f"?{query}"):
        return False
    if canonical_url(url) == canonical_url(base_url):
        return False
    segments = _own_part(path, _route(base_url)[0])
    if not segments or _NOT_ARTICLES.search("/" + "/".join(segments)):
        return False
    if query and not _LONG_NUMBER.search(segments[-1]) and not _DATE_IN_PATH.search(path):
        # A filter of the listing ("?tag=..."), not an article.
        return False
    last = segments[-1]
    words = len(re.split(r"[-_]+", last))
    return bool(
        _DATE_IN_PATH.search(path) or words >= 3 or _LONG_NUMBER.search(last) or len(last) >= 20
    )


def _title(anchor: LexborNode) -> str:
    """The text of the link, or of the heading of the card it is in."""
    text = " ".join(anchor.text(separator=" ", strip=True).split())
    if len(text) >= _MIN_TITLE_CHARS:
        heading = anchor.css_first("h1, h2, h3, h4, h5")
        if heading is not None:
            return " ".join(heading.text(separator=" ", strip=True).split())[:500]
        return text[:500]
    titled = (anchor.attributes.get("title") or anchor.attributes.get("aria-label") or "").strip()
    if len(titled) >= _MIN_TITLE_CHARS:
        return titled[:500]
    card = anchor.parent
    for _ in range(3):
        if card is None:
            break
        heading = card.css_first("h1, h2, h3, h4, h5")
        if heading is not None:
            return " ".join(heading.text(separator=" ", strip=True).split())[:500]
        card = card.parent
    return text


def _date_near(anchor: LexborNode) -> datetime | None:
    """The date of the card the link is in; none from a neighbour's card."""
    card: LexborNode | None = anchor
    for _ in range(4):
        if card is None:
            return None
        stamps = card.css("time[datetime]")
        if len(stamps) > 1:
            # Up to the list itself: the dates are of other cards.
            return None
        if stamps:
            return parse_date(stamps[0].attributes.get("datetime") or "")
        card = card.parent
    return None


def parse_date(text: str) -> datetime | None:
    """An ISO date or timestamp as an aware datetime; a bare date is midnight UTC."""
    value = text.strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _dedupe(links: list[Link]) -> list[Link]:
    seen: dict[str, Link] = {}
    for link in links:
        known = seen.get(link.url)
        if known is None or (not known.title and link.title):
            seen[link.url] = link
    return list(seen.values())[:MAX_LINKS]
