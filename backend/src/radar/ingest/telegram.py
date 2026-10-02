"""Public Telegram channels, read through their web preview at t.me/s/<name>.

The preview is a plain page with the channel's last twenty posts and a link
to the ones before. It needs no account, no API key and no extra service.
A channel whose owner turned the preview off, like one that does not exist,
answers with a redirect to t.me/<name> and cannot be read this way.

Telegram's terms (telegram.org/tos/content-licensing) do not allow taking
channel posts for AI without the owner's consent, so channels are added by
an administrator one by one; DECISIONS.md has the rest.
"""

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from itertools import dropwhile
from urllib.parse import urlsplit

import httpx
from selectolax.lexbor import LexborHTMLParser, LexborNode

from radar.config import get_settings
from radar.images.extract import usable
from radar.ingest.feeds import MAX_TAGS, MAX_URL_LENGTH, SUMMARY_LIMIT, FeedResult
from radar.ingest.net import UnsafeUrlError, safe_get
from radar.ingest.pages import MarkupChanged
from radar.logging import get_logger
from radar.reading import word_count
from radar.store.articles import NewArticle
from radar.text import canonical_url, content_hash, detect_language, split_sentences, truncate

log = get_logger(__name__)

# Five pages are a hundred posts: more than a busy channel writes between runs.
MAX_PAGES = 5
# How far back a channel is read the first time.
FIRST_RUN = timedelta(days=3)
# A post this short that points to a page is the page's teaser.
TEASER_CHARS = 600
# Shorter posts are greetings and captions, not news.
MIN_CHARS = 60
TITLE_LIMIT = 180
# A first sentence shorter than this is half of a headline.
SHORT_TITLE = 30
# A teaser titled shorter than this ("Смотрите тут") says nothing.
MIN_TITLE = 15
# A closing line found in this share of the posts read is the channel's signature.
SIGNATURE_SHARE = 0.3
SIGNATURE_MIN_POSTS = 5
SIGNATURE_LIMIT = 120
PAGE_MAX_BYTES = 3_000_000
# Message numbers are 32-bit in Telegram.
MAX_POST_ID = 2**31 - 1

_TELEGRAM_HOSTS = frozenset({"t.me", "telegram.me", "telegram.dog"})
# A link there is a video or a social post, not a page with an article's text.
_NOT_ARTICLES = frozenset(
    {
        "youtube.com",
        "youtu.be",
        "m.youtube.com",
        "rutube.ru",
        "vk.com",
        "vk.ru",
        "vkvideo.ru",
        "x.com",
        "twitter.com",
        "instagram.com",
        "facebook.com",
        "tiktok.com",
        "max.ru",
    }
)
_NAME = r"[A-Za-z][A-Za-z0-9_]{3,31}"
_NAME_RE = re.compile(_NAME)
_ID_RE = re.compile(r"[0-9]{1,10}")
_POST_PATH_RE = re.compile(rf"/(?:s/)?({_NAME})/([0-9]{{1,10}})/?")
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_BACKGROUND_RE = re.compile(r"background-image:\s*url\(\s*['\"]?([^'\")]+)")
_URL_RE = re.compile(r"https?://\S+")
# Arrows, bullets and stray marks around the words.
_LEAD_RE = re.compile(r"^[^\w«\"„(\[]+")
_TRAIL_RE = re.compile(r"[^\w»\")\]?!…%$€₽+°]+$")
# Emoji are symbols; joiners, keycaps and skin tones glue them together.
_EMOJI_CATEGORIES = frozenset({"So", "Sk", "Cf", "Me"})
_KEPT_SYMBOLS = frozenset("№©®™°")
_VARIATION_SELECTORS = dict.fromkeys(map(ord, "\ufe0e\ufe0f"))
_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200e\u200f\u2060\ufeff"))
# Advertising carries a token and the advertiser's details by law.
_AD_RE = re.compile(
    r"\bРеклама\.?\s+(?:ООО|АО|ПАО|ЗАО|ОАО|ИП|НКО|АНО)\b"
    r"|\bНа правах рекламы\b|\bРекламодатель\s*:|\bПартн[её]рский материал\b"
    r"|\berid\s*[:=]?\s*[A-Za-z0-9]{6,}|#реклама",
    re.IGNORECASE,
)


class ChannelUnavailable(Exception):
    """t.me shows no posts of the channel: there is none, or its preview is off."""


@dataclass(frozen=True, slots=True)
class LinkPreview:
    url: str
    title: str
    description: str
    picture: str | None


@dataclass(frozen=True, slots=True)
class Post:
    channel: str
    id: int
    published_at: datetime
    lines: tuple[str, ...]
    links: tuple[str, ...]
    hashtags: tuple[str, ...]
    picture: str | None
    preview: LinkPreview | None
    forwarded_from: str | None
    is_ad: bool

    @property
    def url(self) -> str:
        return f"https://t.me/{self.channel}/{self.id}"


@dataclass(frozen=True, slots=True)
class ChannelPage:
    title: str
    posts: tuple[Post, ...]


def parse_channel(value: str) -> str:
    """The channel's name from "@name", "name", "t.me/name" or "https://t.me/s/name".

    Names are case-insensitive in Telegram, so the lower-case form is the key.
    """
    text = value.strip()
    if text.startswith("@"):
        text = text[1:]
    elif "/" in text or "." in text:
        parts = urlsplit(text if "://" in text else f"https://{text}")
        host = (parts.hostname or "").removeprefix("www.")
        if parts.scheme not in {"http", "https"} or host not in _TELEGRAM_HOSTS:
            raise ValueError("Нужен адрес канала на t.me или его имя через @.")
        segments = [segment for segment in parts.path.split("/") if segment]
        if segments[:1] == ["s"]:
            segments = segments[1:]
        if len(segments) != 1:
            raise ValueError("Нужен адрес канала, а не отдельного поста.")
        text = segments[0]
    if not _NAME_RE.fullmatch(text):
        raise ValueError("Имя канала - от 5 до 32 латинских букв, цифр и подчёркиваний.")
    return text.lower()


def feed_url(name: str) -> str:
    return f"https://t.me/s/{name}"


def site_url(name: str) -> str:
    return f"https://t.me/{name}"


def is_post_url(url: str) -> bool:
    return _post_of(url) is not None


def _post_of(url: str) -> tuple[str, int] | None:
    parts = urlsplit(url)
    if (parts.hostname or "").removeprefix("www.") not in _TELEGRAM_HOSTS:
        return None
    match = _POST_PATH_RE.fullmatch(parts.path)
    return (match.group(1).lower(), int(match.group(2))) if match else None


# Reading pages


def parse_channel_page(page: str, name: str) -> ChannelPage:
    tree = LexborHTMLParser(page)
    if tree.css_first(".tgme_channel_history") is None:
        raise MarkupChanged("на странице канала нет ленты постов")
    title_node = tree.css_first(".tgme_channel_info_header_title") or tree.css_first(
        ".tgme_header_title"
    )
    return ChannelPage(title=_clean(title_node), posts=_posts(tree, name))


def _posts(tree: LexborHTMLParser, name: str) -> tuple[Post, ...]:
    """The posts of the channel `name` on the page; posts that claim to be
    another channel's are not taken."""
    blocks = [
        block
        for block in tree.css(".tgme_widget_message[data-post]")
        if "service_message" not in (block.attributes.get("class") or "")
    ]
    posts = [post for block in blocks if (post := _post(block, name)) is not None]
    if blocks and not posts:
        raise MarkupChanged(f"не прочитан ни один из {len(blocks)} постов")
    return tuple(posts)


def _post(block: LexborNode, name: str) -> Post | None:
    channel, _, number = (block.attributes.get("data-post") or "").partition("/")
    stamp = block.css_first(".tgme_widget_message_date time[datetime]")
    if (
        channel.lower() != name
        or not _ID_RE.fullmatch(number)
        or int(number) > MAX_POST_ID
        or stamp is None
    ):
        return None
    try:
        published = datetime.fromisoformat(stamp.attributes.get("datetime") or "")
    except ValueError:
        return None
    if published.tzinfo is None:
        published = published.replace(tzinfo=UTC)

    # The post's own text; a quoted reply carries js-message_reply_text instead.
    body = block.css_first(".js-message_text")
    lines: tuple[str, ...] = ()
    links: list[str] = []
    hashtags: list[str] = []
    if body is not None:
        lines = _lines(body)
        for anchor in body.css("a[href]"):
            href = _href(anchor)
            label = anchor.text().strip()
            if label.startswith("#") and not href.startswith("http"):
                hashtags.append(label[1:])
            elif _external(href):
                links.append(href)
    hrefs = "\n".join(_href(anchor) for anchor in block.css("a[href]"))
    forwarded = block.css_first(".tgme_widget_message_forwarded_from_name")
    return Post(
        channel=channel,
        id=int(number),
        published_at=published,
        lines=tuple(line for line in lines if not _only_hashtags(line)),
        links=tuple(links),
        hashtags=tuple(dict.fromkeys(tag for tag in hashtags if tag))[:MAX_TAGS],
        picture=_first_background(
            block, ".tgme_widget_message_photo_wrap", ".tgme_widget_message_video_thumb"
        ),
        preview=_preview(block),
        forwarded_from=_clean(forwarded) or None,
        # The marker may sit in a caption or a link's card, not only in the text.
        is_ad=bool(_AD_RE.search(f"{block.text()}\n{hrefs}")),
    )


def _lines(node: LexborNode) -> tuple[str, ...]:
    """The text by paragraph: Telegram marks line breaks with <br>."""
    fragment = LexborHTMLParser(_BR_RE.sub("\n", node.html or ""))
    raw = (fragment.body.text() if fragment.body else "").translate(_INVISIBLE)
    return tuple(line for line in (" ".join(part.split()) for part in raw.split("\n")) if line)


def _clean(node: LexborNode | None) -> str:
    return " ".join(node.text().translate(_INVISIBLE).split()) if node is not None else ""


def _only_hashtags(line: str) -> bool:
    return all(word.startswith("#") for word in line.split())


def _href(anchor: LexborNode) -> str:
    # t.me escapes the ampersands in links twice. Only that is undone: a full
    # unescape would read "&sect=" in a query as "§=".
    return (anchor.attributes.get("href") or "").replace("&amp;", "&").strip()


def _host(href: str) -> str:
    return (urlsplit(href).hostname or "").removeprefix("www.")


def _external(href: str) -> bool:
    try:
        parts = urlsplit(href)
        host = (parts.hostname or "").removeprefix("www.")
    except ValueError:
        # "http://[::1" and the like: no address at all.
        return False
    return (
        parts.scheme in {"http", "https"}
        and bool(host)
        and host not in _TELEGRAM_HOSTS
        and len(href) <= MAX_URL_LENGTH
    )


def _first_background(block: LexborNode, *selectors: str) -> str | None:
    for selector in selectors:
        for node in block.css(selector):
            match = _BACKGROUND_RE.search(node.attributes.get("style") or "")
            if match and (url := usable(match.group(1))):
                return url
    return None


def _preview(block: LexborNode) -> LinkPreview | None:
    node = block.css_first("a.tgme_widget_message_link_preview")
    if node is None or not _external(href := _href(node)):
        return None
    return LinkPreview(
        url=href,
        title=_clean(node.css_first(".link_preview_title")),
        description=_clean(node.css_first(".link_preview_description")),
        picture=_first_background(node, ".link_preview_image", ".link_preview_right_image"),
    )


# Posts as articles


def signatures(posts: Sequence[Post]) -> frozenset[str]:
    """The closing lines the channel signs its posts with ("Подписывайтесь…").

    Counted over every post read in a run, so that one or two new posts are
    cleaned by what the page around them shows.
    """
    if len(posts) < SIGNATURE_MIN_POSTS:
        return frozenset()
    counts = Counter(
        line for post in posts for line in set(post.lines[-2:]) if len(line) <= SIGNATURE_LIMIT
    )
    floor = max(3, math.ceil(len(posts) * SIGNATURE_SHARE))
    return frozenset(line for line, count in counts.items() if count >= floor)


def articles_of(
    posts: Iterable[Post], language: str, now: datetime, signed: frozenset[str] = frozenset()
) -> tuple[NewArticle, ...]:
    """The posts as articles, newest first; two posts that point to one page
    give one article."""
    articles: dict[str, NewArticle] = {}
    for post in sorted(posts, key=lambda post: post.id, reverse=True):
        # A signature closes a post; the same line in the middle is the text's own.
        lines = tuple(reversed(list(dropwhile(signed.__contains__, reversed(post.lines)))))
        article = to_article(replace(post, lines=lines), language, now)
        if article is not None and article.url not in articles:
            articles[article.url] = article
    return tuple(articles.values())


# Enough for a card; a post of a hundred links is a list, not news.
MAX_POST_LINKS = 10


def to_article(post: Post, language: str, now: datetime) -> NewArticle | None:
    """The post as an article, or the page it is a teaser for; None for
    advertising and for posts with nothing to read."""
    if post.is_ad:
        return None
    link = _main_link(post)
    own = [line for line in post.lines if not (link and _URL_RE.fullmatch(line))]
    own_text = " ".join(own)
    if link and len(own_text) < TEASER_CHARS:
        return _teaser(post, link, own, language, now)
    title, body = _title_and_body(own)
    if len(own_text) < MIN_CHARS or not title:
        return None
    content = "\n".join(own)
    return NewArticle(
        url=post.url,
        title=title,
        summary=truncate(" ".join(body), SUMMARY_LIMIT),
        content=content,
        author=post.forwarded_from,
        tags=post.hashtags,
        language=_language(language, content),
        published_at=min(post.published_at, now),
        content_hash=content_hash(title, content),
        image_url=post.picture or (post.preview.picture if post.preview else None),
        word_count=word_count(content),
        # What the post cites: the dataset's card of a channel post lists it.
        links=tuple(dict.fromkeys(post.links))[:MAX_POST_LINKS],
    )


def _main_link(post: Post) -> str | None:
    """The article the post points to: its link preview, or a bare address
    on the last line. A video or a social post is not one."""
    link = None
    if post.preview is not None:
        link = post.preview.url
    elif post.lines and post.links and _URL_RE.fullmatch(post.lines[-1]):
        link = post.links[-1]
    return link if link and _host(link) not in _NOT_ARTICLES else None


def _teaser(
    post: Post, link: str, own: list[str], language: str, now: datetime
) -> NewArticle | None:
    preview = post.preview if post.preview and post.preview.url == link else None
    title, body = _title_and_body(own)
    summary = " ".join(body)
    if len(title) < SHORT_TITLE and preview is not None and preview.title:
        # "Читать по ссылке": the card Telegram drew for the link says more.
        title, summary = preview.title, preview.description or " ".join(own)
    if len(title) < MIN_TITLE:
        return None
    summary = truncate(summary or (preview.description if preview else ""), SUMMARY_LIMIT)
    return NewArticle(
        url=canonical_url(link),
        title=title,
        summary=summary,
        # The page's own text is fetched later, when the source asks for it.
        content=None,
        author=post.forwarded_from,
        tags=post.hashtags,
        language=_language(language, f"{title} {summary}"),
        published_at=min(post.published_at, now),
        content_hash=content_hash(title, summary),
        image_url=post.picture or (preview.picture if preview else None),
    )


def _title_and_body(lines: list[str]) -> tuple[str, list[str]]:
    """The first sentence of the first paragraph, and what is left.

    A short first sentence is a headline in two parts ("Ядреная веб-бомба.
    Разбираем RCE в WordPress"), so the whole paragraph is taken then.
    Lines of emoji or links alone are skipped.
    """
    lines = list(dropwhile(lambda line: not _plain(line), lines))
    if not lines:
        return "", []
    first = _plain(lines[0])
    title = (split_sentences(first) or [first])[0]
    if len(title) < SHORT_TITLE and len(first) <= TITLE_LIMIT:
        title = first
    rest = first[len(title) :].strip()
    body = [rest, *lines[1:]] if rest else list(lines[1:])
    if len(title) > TITLE_LIMIT:
        # A cut title loses words, so the body keeps the whole paragraph.
        title, body = truncate(title, TITLE_LIMIT), [first, *lines[1:]]
    return _TRAIL_RE.sub("", title), body


def _plain(line: str) -> str:
    """The line without emoji and links: they belong to a post, not a headline."""
    composed = unicodedata.normalize("NFC", _URL_RE.sub(" ", line)).translate(_VARIATION_SELECTORS)
    kept = "".join(
        char
        for char in composed
        if char in _KEPT_SYMBOLS or unicodedata.category(char) not in _EMOJI_CATEGORIES
    )
    return _LEAD_RE.sub("", " ".join(kept.split()))


def _language(language: str, text: str) -> str:
    return language if language in {"ru", "en"} else detect_language(text[:500])


# Fetching


async def fetch_channel(
    client: httpx.AsyncClient, url: str, *, language: str, last_post_id: int | None
) -> FeedResult:
    """New posts of a channel since the last one read.

    A channel read for the first time gives the posts of the last few days,
    or its last page when it has been quiet longer.
    """
    name = parse_channel(url)
    now = datetime.now(UTC)
    read = await _read_pages(client, name, last_post_id, now)
    if last_post_id is None:
        fresh = [post for post in read if post.published_at >= now - FIRST_RUN] or read
    else:
        fresh = [post for post in read if post.id > last_post_id]
    if not fresh:
        return FeedResult(status="not_modified", last_post_id=last_post_id)
    return FeedResult(
        status="ok",
        articles=articles_of(fresh, language, now, signatures(read)),
        last_post_id=max(post.id for post in read),
    )


async def _read_pages(
    client: httpx.AsyncClient, name: str, last_post_id: int | None, now: datetime
) -> list[Post]:
    """Pages from the newest back to the last post read, or to FIRST_RUN ago."""
    read: dict[int, Post] = {}
    before: int | None = None
    for _ in range(MAX_PAGES):
        posts = (await _channel_page(client, name, before)).posts
        if not posts:
            return list(read.values())
        read.update((post.id, post) for post in posts)
        oldest = min(posts, key=lambda post: post.id)
        if last_post_id is None and oldest.published_at < now - FIRST_RUN:
            return list(read.values())
        if last_post_id is not None and oldest.id <= last_post_id:
            return list(read.values())
        before = oldest.id
    if last_post_id is not None:
        # More than a hundred posts since the last run: the rest are skipped.
        log.warning("telegram_posts_skipped", channel=name, after=last_post_id, before=before)
    return list(read.values())


async def channel_title(client: httpx.AsyncClient, name: str) -> str:
    """The channel's name as its owner wrote it; raises when it cannot be read."""
    return (await _channel_page(client, name, None)).title or name


async def post_picture(client: httpx.AsyncClient, url: str) -> str | None:
    """The current address of a post's picture.

    Addresses on Telegram's CDN stop working after a while, so a stored one
    is looked up again here. The post's page is no help: for a post without
    a photo its og:image is the channel's avatar.
    """
    post = _post_of(url)
    if post is None:
        return None
    response = await _get(client, f"/{post[0]}/{post[1]}?embed=1&mode=tme")
    posts = _posts(LexborHTMLParser(response.text), post[0])
    if not posts:
        return None
    first = posts[0]
    return first.picture or (first.preview.picture if first.preview else None)


async def _channel_page(client: httpx.AsyncClient, name: str, before: int | None) -> ChannelPage:
    response = await _get(client, f"/s/{name}" + (f"?before={before}" if before else ""))
    # A channel without a preview redirects to its card at t.me/<name>.
    path = urlsplit(str(response.request.url)).path.rstrip("/").lower()
    if not path.endswith(f"/s/{name}"):
        raise ChannelUnavailable(
            f"t.me не показывает посты @{name}: канала нет или у него закрыто веб-превью"
        )
    return parse_channel_page(response.text, name)


async def _get(client: httpx.AsyncClient, path: str) -> httpx.Response:
    """The page from the first preview host that answers.

    t.me itself is the first; telegram.me serves the same pages and stays up
    when t.me's domain has trouble, and a mirror can be added for networks
    where Telegram is blocked. A refusal (404 and the like) is an answer and
    is not asked again elsewhere.
    """
    error: Exception | None = None
    for base in get_settings().telegram_preview_urls:
        try:
            response = await safe_get(client, base.rstrip("/") + path, max_bytes=PAGE_MAX_BYTES)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code < 500 and exc.response.status_code != 429:
                raise
            error = exc
        except (httpx.TransportError, TimeoutError, UnsafeUrlError) as exc:
            error = exc
        else:
            return response
    raise error or ChannelUnavailable("не задан ни один адрес веб-превью Telegram")
