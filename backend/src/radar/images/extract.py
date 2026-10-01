"""Where an article's picture is: in the feed entry, or in the page's metadata.

Most feeds carry a picture (media:content, media:thumbnail, an enclosure, or
an <img> in the summary). Those that do not still set og:image on the page,
which is read once, from the head only.
"""

from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit

MAX_URL = 2000
# Not pictures of the story: icons, counters, vector logos, the stand-in a
# site shows when a story has no picture of its own.
_SKIP_PARTS = (
    "favicon",
    "pixel",
    "spacer",
    "1x1",
    "/logo",
    "logo.",
    "avatar",
    "gravatar",
    "placeholder",
    "no-image",
    "no_image",
    "noimage",
    "default-image",
    "default_image",
)
_SKIP_EXTENSIONS = (".svg", ".ico", ".svgz")
_PAGE_PROPERTIES = (
    "og:image:secure_url",
    "og:image",
    "og:image:url",
    "twitter:image",
    "twitter:image:src",
)


def usable(url: str | None, base: str = "") -> str | None:
    """An absolute http(s) picture address that is likely the story's own."""
    if not url:
        return None
    url = urljoin(base, url.strip()) if base else url.strip()
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname or len(url) > MAX_URL:
        return None
    lowered = url.lower()
    if parts.path.lower().endswith(_SKIP_EXTENSIONS) or any(
        part in lowered for part in _SKIP_PARTS
    ):
        return None
    if any(char.isspace() or char in "<>\"'" for char in url):
        return None
    return url


class _FirstImage(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.found is None and tag == "img":
            values = dict(attrs)
            if values.get("width") in {"1", "0"} or values.get("height") in {"1", "0"}:
                return
            self.found = values.get("src") or values.get("data-src")


def first_img(html: str, base: str = "") -> str | None:
    parser = _FirstImage()
    parser.feed(html)
    return usable(parser.found, base)


def _is_image(item: dict[str, Any]) -> bool:
    kind = str(item.get("type") or item.get("medium") or "")
    return kind.startswith("image") or (kind == "" and bool(item.get("url") or item.get("href")))


def from_entry(entry: Any, base: str = "") -> str | None:
    """The picture a feed entry carries, if any."""
    for key in ("media_content", "media_thumbnail"):
        for item in entry.get(key) or []:
            if isinstance(item, dict) and _is_image(item):
                found = usable(item.get("url"), base)
                if found:
                    return found
    for link in entry.get("links") or []:
        if (
            isinstance(link, dict)
            and link.get("rel") == "enclosure"
            and str(link.get("type", "")).startswith("image")
        ):
            found = usable(link.get("href"), base)
            if found:
                return found
    image = entry.get("image")
    if isinstance(image, dict):
        found = usable(image.get("href") or image.get("url"), base)
        if found:
            return found
    for text in (
        entry.get("summary") or "",
        *(part.get("value", "") for part in entry.get("content") or []),
    ):
        if "<img" in text:
            found = first_img(text, base)
            if found:
                return found
    return None


class _HeadImage(HTMLParser):
    """og:image and friends from the head; parsing stops at <body>."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.candidates: dict[str, str] = {}
        self.done = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.done:
            return
        if tag == "body":
            self.done = True
            return
        values = {key: value or "" for key, value in attrs}
        if tag == "meta":
            name = (values.get("property") or values.get("name") or "").lower()
            if name in _PAGE_PROPERTIES and values.get("content"):
                self.candidates.setdefault(name, values["content"])
        elif tag == "link" and values.get("rel", "").lower() == "image_src" and values.get("href"):
            self.candidates.setdefault("image_src", values["href"])


def from_page(html: str, base: str) -> str | None:
    """The picture a page declares for sharing."""
    parser = _HeadImage()
    parser.feed(html[:400_000])
    for name in (*_PAGE_PROPERTIES, "image_src"):
        found = usable(parser.candidates.get(name), base)
        if found:
            return found
    return None
