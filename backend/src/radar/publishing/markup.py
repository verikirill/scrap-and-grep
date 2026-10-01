"""Post markup: one safe HTML subset in, Telegram's two dialects out.

Posts are kept in a small HTML subset: paragraphs, two heading levels, lists,
quotes, preformatted text, and inline bold, italic, underline, strikethrough,
code, spoilers and links. Whatever comes in, from the model or from the
editor in the browser, is parsed and rebuilt from an allowlist, so a post can
only ever contain these tags with escaped text.

Telegram reads two dialects. A classic post (sendMessage, sendPhoto) knows
only inline tags and blockquote; blocks become line breaks and bullets. A
rich post (sendRichMessage, Bot API 10.1) keeps the blocks as they are.
"""

from dataclasses import dataclass, field
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlsplit

BLOCKS = frozenset({"p", "h2", "h3", "ul", "ol", "li", "blockquote", "pre"})
INLINE = frozenset({"b", "i", "u", "s", "code", "a", "tg-spoiler", "br"})
_ALIASES = {
    "strong": "b",
    "em": "i",
    "ins": "u",
    "del": "s",
    "strike": "s",
    "h1": "h2",
    "h4": "h3",
    "h5": "h3",
    "h6": "h3",
}
_VOID = frozenset({"br"})
_SKIPPED = frozenset({"script", "style", "template", "noscript", "iframe", "object", "svg"})
_LINK_SCHEMES = frozenset({"http", "https", "tg"})
# Telegram counts characters after the markup is parsed.
TEXT_LIMIT = 4096
CAPTION_LIMIT = 1024
RICH_LIMIT = 32768


def safe_url(url: str) -> str | None:
    """A link Telegram will open without surprises: http(s) or tg, with a host."""
    url = url.strip()
    parts = urlsplit(url)
    if parts.scheme not in _LINK_SCHEMES or not (parts.netloc or parts.scheme == "tg"):
        return None
    if any(char.isspace() or char in "<>\"'" for char in url):
        return None
    return url


@dataclass
class Node:
    tag: str
    children: list[Node | str] = field(default_factory=list)
    href: str | None = None


class _Builder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack: list[Node] = [self.root]
        # Whether each open <span> is a spoiler, so that </span> closes the
        # right thing.
        self.spans: list[bool] = []
        # Inside <script> and the like nothing is text.
        self.skipping = 0

    def _current(self) -> Node:
        return self.stack[-1]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIPPED:
            self.skipping += 1
            return
        tag = _ALIASES.get(tag, tag)
        if tag == "span":
            is_spoiler = ("class", "tg-spoiler") in attrs or ("data-type", "spoiler") in attrs
            self.spans.append(is_spoiler)
            if not is_spoiler:
                return
            tag = "tg-spoiler"
        if tag not in BLOCKS and tag not in INLINE:
            return
        if tag in BLOCKS:
            # A block cannot sit inside inline markup; close the inline tags.
            while self._current().tag in INLINE:
                self.stack.pop()
            if tag == "li" and self._current().tag not in {"ul", "ol"}:
                self._open(Node("ul"))
        node = Node(tag)
        if tag == "a":
            node.href = safe_url(dict(attrs).get("href") or "")
        self._current().children.append(node)
        if tag not in _VOID:
            self.stack.append(node)

    def _open(self, node: Node) -> None:
        self._current().children.append(node)
        self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIPPED:
            self.skipping = max(0, self.skipping - 1)
            return
        tag = _ALIASES.get(tag, tag)
        if tag == "span":
            if not self.spans or not self.spans.pop():
                return
            tag = "tg-spoiler"
        for depth in range(len(self.stack) - 1, 0, -1):
            if self.stack[depth].tag == tag:
                del self.stack[depth:]
                return

    def handle_data(self, data: str) -> None:
        if data and not self.skipping:
            self._current().children.append(data)


def parse(html: str) -> list[Node | str]:
    builder = _Builder()
    builder.feed(html)
    builder.close()
    return _tidy(builder.root.children)


def _tidy(children: list[Node | str]) -> list[Node | str]:
    """Top-level text and inline tags go into paragraphs; empty blocks go."""
    tidy: list[Node | str] = []
    loose: list[Node | str] = []

    def flush() -> None:
        if any(_text_of(item).strip() for item in loose):
            tidy.append(Node("p", list(loose)))
        loose.clear()

    for child in children:
        if isinstance(child, Node) and child.tag in BLOCKS:
            flush()
            if _text_of(child).strip():
                tidy.append(child)
        else:
            loose.append(child)
    flush()
    return tidy


def _text_of(item: Node | str) -> str:
    if isinstance(item, str):
        return item
    if item.tag == "br":
        return "\n"
    text = "".join(_text_of(child) for child in item.children)
    return f"{text}\n" if item.tag == "li" else text


def plain_text(html: str) -> str:
    """The words of a post, for checks and comparisons."""
    return "\n".join(_text_of(node).strip() for node in parse(html)).strip()


def _inline(items: list[Node | str]) -> str:
    out = []
    for item in items:
        if isinstance(item, str):
            out.append(escape(item, quote=False))
        elif item.tag == "br":
            out.append("\n")
        elif item.tag in BLOCKS:
            out.append(_inline(item.children))
        elif item.tag == "a":
            inner = _inline(item.children)
            out.append(f'<a href="{escape(item.href)}">{inner}</a>' if item.href else inner)
        else:
            out.append(f"<{item.tag}>{_inline(item.children)}</{item.tag}>")
    return "".join(out)


def _block_html(node: Node) -> str:
    if node.tag in {"ul", "ol"}:
        items = [child for child in node.children if isinstance(child, Node) and child.tag == "li"]
        inner = "".join(f"<li>{_inline(item.children).strip()}</li>" for item in items)
        return f"<{node.tag}>{inner}</{node.tag}>"
    if node.tag == "blockquote":
        inner = (
            "".join(
                _block_html(child) if isinstance(child, Node) and child.tag in BLOCKS else ""
                for child in node.children
            )
            or f"<p>{_inline(node.children).strip()}</p>"
        )
        return f"<blockquote>{inner}</blockquote>"
    return f"<{node.tag}>{_inline(node.children).strip()}</{node.tag}>"


def canonical(html: str) -> str:
    """The post rebuilt from the allowlist: what is stored and edited."""
    return "".join(
        _block_html(node) if isinstance(node, Node) else escape(node) for node in parse(html)
    )


def _classic_block(node: Node) -> str:
    if node.tag in {"ul", "ol"}:
        items = [child for child in node.children if isinstance(child, Node) and child.tag == "li"]
        lines = [
            f"{f'{number}.' if node.tag == 'ol' else '•'} {_inline(item.children).strip()}"
            for number, item in enumerate(items, start=1)
        ]
        return "\n".join(lines)
    if node.tag in {"h2", "h3"}:
        return f"<b>{_inline(node.children).strip()}</b>"
    if node.tag == "blockquote":
        parts = [
            _classic_block(child) if isinstance(child, Node) else escape(child)
            for child in node.children
        ]
        inner = "\n".join(part.strip() for part in parts if part.strip())
        return f"<blockquote>{inner}</blockquote>"
    if node.tag == "pre":
        return f"<pre>{escape(_text_of(node).strip(), quote=False)}</pre>"
    return _inline(node.children).strip()


def to_classic(html: str) -> str:
    """Telegram HTML for sendMessage and captions: blocks as blank lines."""
    blocks = [_classic_block(node) for node in parse(html) if isinstance(node, Node)]
    return "\n\n".join(block for block in blocks if block)


def to_rich(html: str) -> str:
    """Telegram rich HTML for sendRichMessage: the blocks stay blocks."""
    return canonical(html)


def visible_length(telegram_html: str) -> int:
    """Characters Telegram counts against its limits: text after the tags."""
    builder = _Builder()
    builder.feed(telegram_html)
    builder.close()
    return len(_text_of(builder.root))
