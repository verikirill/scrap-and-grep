"""An article as blocks: paragraphs, headings, lists, quotes, code, tables
and pictures.

The blocks are plain data taken from trafilatura's tree of the page, never
the page's HTML: the browser draws them with its own elements, so nothing a
site wrote runs or styles anything in the app. A picture is named by a hash
of its address, and the API serves only the addresses listed here.
"""

import hashlib
import re
import textwrap
from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import Literal, NotRequired, TypedDict
from urllib.parse import urlsplit

from lxml.etree import _Element

from radar.images.extract import usable

MAX_BLOCKS = 500
MAX_CHARS = 150_000
MAX_IMAGES = 40
MAX_LIST_ITEMS = 200
MAX_TABLE_ROWS = 80
MAX_TABLE_COLUMNS = 10
MAX_CELL = 500
MAX_HEADING = 300
MAX_CODE = 20_000
MAX_ALT = 300
MAX_URL = 2000
# Less text than this is a stub, an error page or a paywall, not the article.
MIN_CHARS = 200
# The feed's picture leads the text unless the page shows one of its own this early.
LEAD_WITHIN = 3

_LEVELS: dict[str, Literal[2, 3, 4, 5]] = {"h1": 2, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 5}
_SPACE_RE = re.compile(r"[^\S\n]+")
_NEWLINES_RE = re.compile(r" *\n[\n ]*")
_LINE_NUMBER_RE = re.compile(r"\d{1,5}")
_URL_RE = re.compile(r"https?://[^\s<>\"'«»]+")
_URL_TAIL = ".,;:!?)]»\"'"
# "Уязвимое ПО: ..." - the name of a field at the start of a line.
_LABEL_RE = re.compile(r"([^\W\d][^:.\d]{1,40}):\s")
# Kinds of blocks; a wrapper holding one of them is read block by block.
_BLOCK_TAGS = {"p", "head", "list", "table", "quote", "code", "graphic"}


class Span(TypedDict):
    text: str
    b: NotRequired[bool]
    i: NotRequired[bool]
    code: NotRequired[bool]
    href: NotRequired[str]


class Paragraph(TypedDict):
    type: Literal["p"]
    spans: list[Span]


class Heading(TypedDict):
    type: Literal["h"]
    level: Literal[2, 3, 4, 5]
    text: str


class Items(TypedDict):
    type: Literal["list"]
    ordered: bool
    items: list[list[Span]]


class Quote(TypedDict):
    type: Literal["quote"]
    spans: list[Span]


class Code(TypedDict):
    type: Literal["code"]
    text: str


class Image(TypedDict):
    type: Literal["image"]
    id: str
    alt: NotRequired[str]


class Table(TypedDict):
    type: Literal["table"]
    head: list[str] | None
    rows: list[list[str]]


Block = Paragraph | Heading | Items | Quote | Code | Image | Table


@dataclass(frozen=True, slots=True)
class Body:
    blocks: list[Block]
    # The pictures' addresses by the names their blocks carry.
    images: dict[str, str]
    # Characters of text, to tell an article from a stub.
    chars: int


@dataclass(frozen=True, slots=True)
class _Marks:
    b: bool = False
    i: bool = False
    code: bool = False
    href: str | None = None


type _Token = tuple[str, _Marks] | _Element


def image_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def link(target: str | None) -> str | None:
    """An address a reader may follow: absolute http(s) and nothing else."""
    if not target:
        return None
    target = target.strip()
    parts = urlsplit(target)
    if parts.scheme not in {"http", "https"} or not parts.hostname or len(target) > MAX_URL:
        return None
    if any(char.isspace() or char in "<>\"'" for char in target):
        return None
    return target


def plain_text(blocks: Iterable[Block]) -> str:
    """The prose of the blocks, for counting words; code and tables are not read so."""
    lines: list[str] = []
    for block in blocks:
        if block["type"] == "h":
            lines.append(block["text"])
        elif block["type"] == "p" or block["type"] == "quote":
            lines.append(_joined(block["spans"]))
        elif block["type"] == "list":
            lines.extend(_joined(item) for item in block["items"])
    return "\n".join(lines)


def from_tree(body: _Element, *, title: str, lead: str | None) -> Body:
    """The blocks of trafilatura's tree of a page (the body of bare_extraction)."""
    builder = _Builder(title)
    _children(builder, body)
    return builder.finish(lead)


def from_text(text: str, *, title: str, lead: str | None, labelled: bool = False) -> Body:
    """A paragraph per line of plain text, with its addresses as links.

    `labelled` text has a field name before a colon on every line but the
    first ("Уязвимое ПО: ..."); the name is set in bold.
    """
    builder = _Builder(title)
    lines = (" ".join(line.split()) for line in text.splitlines())
    for number, line in enumerate(line for line in lines if line):
        builder.paragraph(_linked(line, labelled=labelled and number > 0))
    return builder.finish(lead)


class _Builder:
    def __init__(self, title: str) -> None:
        self.blocks: list[Block] = []
        self.images: dict[str, str] = {}
        self.chars = 0
        self._title = _key(title)

    @property
    def full(self) -> bool:
        return len(self.blocks) >= MAX_BLOCKS or self.chars >= MAX_CHARS

    def text(self, block: Block) -> None:
        size = _block_size(block)
        if size and not self.full:
            self.blocks.append(block)
            self.chars += size

    def paragraph(self, spans: list[Span], *, quote: bool = False) -> None:
        if quote:
            self.text({"type": "quote", "spans": spans})
        else:
            self.text({"type": "p", "spans": spans})

    def image(self, element: _Element) -> None:
        url = usable(element.get("src"))
        if url is None or self.full or len(self.images) >= MAX_IMAGES:
            return
        name = image_id(url)
        if name in self.images:
            return
        self.images[name] = url
        block: Image = {"type": "image", "id": name}
        if alt := " ".join((element.get("alt") or "").split())[:MAX_ALT]:
            block["alt"] = alt
        self.blocks.append(block)

    def finish(self, lead: str | None) -> Body:
        blocks = _without_empty_sections(_without_title(self.blocks, self._title))
        images = dict(self.images)
        lead_url = usable(lead)
        if (
            lead_url
            and image_id(lead_url) not in images
            and not any(block["type"] == "image" for block in blocks[:LEAD_WITHIN])
        ):
            name = image_id(lead_url)
            images[name] = lead_url
            blocks = [{"type": "image", "id": name}, *blocks]
        # Counted again: the headline and empty headings are gone.
        chars = sum(_block_size(block) for block in blocks)
        return Body(blocks=blocks, images=images, chars=chars)


# The tree


def _children(builder: _Builder, element: _Element) -> None:
    for child in element:
        if builder.full:
            return
        _block(builder, child)
        if child.tail and child.tail.strip():
            builder.paragraph(_tidy([(child.tail, _Marks())]))


def _block(builder: _Builder, element: _Element) -> None:
    tag = element.tag if isinstance(element.tag, str) else ""
    if tag in {"p", "quote"}:
        _flow(builder, element, quote=tag == "quote")
    elif tag == "head":
        if text := _plain(element)[:MAX_HEADING]:
            level = _LEVELS.get(element.get("rend") or "", 3)
            builder.text({"type": "h", "level": level, "text": text})
    elif tag == "list":
        _list(builder, element)
    elif tag == "code":
        _code(builder, "".join(element.itertext()))
    elif tag == "graphic":
        builder.image(element)
    elif tag == "table":
        _table(builder, element)
    elif tag and tag != "lb":
        # A wrapper (div and the like): its blocks, or its text as a paragraph.
        if any(child.tag in _BLOCK_TAGS for child in element):
            if element.text and element.text.strip():
                builder.paragraph(_tidy([(element.text, _Marks())]))
            _children(builder, element)
        else:
            _flow(builder, element, quote=False)


def _flow(builder: _Builder, element: _Element, *, quote: bool) -> None:
    """A paragraph, or a quote. A picture, list or table inside it becomes a
    block of its own, in place."""
    run: list[tuple[str, _Marks]] = []
    for token in _inline(element):
        if isinstance(token, _Element):
            builder.paragraph(_tidy(run), quote=quote)
            run = []
            _block(builder, token)
        else:
            run.append(token)
    builder.paragraph(_tidy(run), quote=quote)


def _list(builder: _Builder, element: _Element) -> None:
    """A list; a nested one is read as more items of it. Pictures and tables
    in its items follow it."""
    items: list[list[Span]] = []
    after: list[_Element] = []
    for item in element.iter("item"):
        run: list[tuple[str, _Marks]] = []
        for token in _inline(item):
            if not isinstance(token, _Element):
                run.append(token)
            elif token.tag != "list":
                after.append(token)
        if spans := _tidy(run):
            items.append(spans)
    if items:
        ordered = element.get("rend") == "ol"
        builder.text({"type": "list", "ordered": ordered, "items": items[:MAX_LIST_ITEMS]})
    for nested in after:
        _block(builder, nested)


def _code(builder: _Builder, raw: str) -> None:
    lines = [line.rstrip() for line in raw.replace("\r", "").strip("\n").split("\n")]
    text = textwrap.dedent("\n".join(lines)).strip("\n")[:MAX_CODE]
    # The first line often keeps the indent of the tag it followed.
    text = text.lstrip(" ")
    if text.strip():
        builder.text({"type": "code", "text": text})


def _table(builder: _Builder, element: _Element) -> None:
    rows = [row.findall("cell") for row in element.findall("row")]
    rows = [cells for cells in rows if any(_plain(cell) for cell in cells)]
    if not rows:
        return
    texts = [[_plain(cell)[:MAX_CELL] for cell in cells] for cells in rows]
    if all(len(cells) == 2 and _LINE_NUMBER_RE.fullmatch(cells[0]) for cells in texts):
        # A code listing, with its line numbers in a column of their own.
        _code(builder, "\n".join("".join(cells[1].itertext()).strip("\n") for cells in rows))
        return
    width = min(max(len(cells) for cells in texts), MAX_TABLE_COLUMNS)
    if width == 1 or len(rows) == 1:
        # Laid out as a table, read as paragraphs.
        for cells in rows:
            for cell in cells:
                _flow(builder, cell, quote=False)
        return
    head = None
    if all(cell.get("role") == "head" for cell in rows[0]):
        head, texts = _padded(texts[0], width), texts[1:]
    body = [_padded(cells, width) for cells in texts[:MAX_TABLE_ROWS]]
    if body:
        builder.text({"type": "table", "head": head, "rows": body})


def _padded(cells: list[str], width: int) -> list[str]:
    return (cells + [""] * width)[:width]


def _inline(element: _Element) -> list[_Token]:
    """The element's text with its marks, and the pictures, lists and tables in it."""
    tokens: list[_Token] = []
    _walk(element, _Marks(), tokens)
    return tokens


def _walk(node: _Element, marks: _Marks, tokens: list[_Token]) -> None:
    if node.text:
        tokens.append((node.text, marks))
    for child in node:
        tag = child.tag if isinstance(child.tag, str) else ""
        if tag in {"graphic", "list", "table"}:
            tokens.append(child)
        elif tag == "lb":
            tokens.append(("\n", marks))
        elif tag:
            if tag == "p" and tokens:
                tokens.append(("\n", marks))
            _walk(child, _marked(child, marks), tokens)
        if child.tail:
            tokens.append((child.tail, marks))


def _marked(element: _Element, marks: _Marks) -> _Marks:
    rend = element.get("rend") or ""
    if element.tag == "hi" and rend == "#b":
        return replace(marks, b=True)
    if element.tag == "hi" and rend == "#i":
        return replace(marks, i=True)
    if element.tag == "code" or (element.tag == "hi" and rend == "#t"):
        return replace(marks, code=True)
    if element.tag == "ref" and (href := link(element.get("target"))):
        return replace(marks, href=href)
    return marks


def _tidy(run: Iterable[tuple[str, _Marks]]) -> list[Span]:
    """Spans with the page's whitespace collapsed; line breaks are kept."""
    merged: list[tuple[str, _Marks]] = []
    for raw, marks in run:
        if merged and merged[-1][1] == marks:
            merged[-1] = (merged[-1][0] + raw, marks)
        else:
            merged.append((raw, marks))
    joined: list[tuple[str, _Marks]] = []
    for raw, marks in merged:
        text = _NEWLINES_RE.sub("\n", _SPACE_RE.sub(" ", raw.replace("\r", "")))
        before = joined[-1][0] if joined else "\n"
        if before.endswith("\n"):
            text = text.lstrip(" \n")
        elif before.endswith(" "):
            text = text.lstrip(" ")
        if text.startswith("\n") and joined:
            joined[-1] = (joined[-1][0].rstrip(" "), joined[-1][1])
        if text:
            joined.append((text, marks))
    while joined and not joined[0][0].strip():
        joined.pop(0)
    while joined and not joined[-1][0].strip():
        joined.pop()
    if not joined:
        return []
    joined[0] = (joined[0][0].lstrip(), joined[0][1])
    joined[-1] = (joined[-1][0].rstrip(), joined[-1][1])
    return [_span(text, marks) for text, marks in joined]


def _span(text: str, marks: _Marks) -> Span:
    span: Span = {"text": text}
    if marks.b:
        span["b"] = True
    if marks.i:
        span["i"] = True
    if marks.code:
        span["code"] = True
    if marks.href:
        span["href"] = marks.href
    return span


def _linked(line: str, *, labelled: bool) -> list[Span]:
    spans: list[Span] = []
    rest = line
    if labelled and (label := _LABEL_RE.match(line)):
        spans.append({"text": f"{label.group(1)}:", "b": True})
        rest = f" {line[label.end() :]}"
    position = 0
    for match in _URL_RE.finditer(rest):
        address = _address(match.group())
        if match.start() > position:
            spans.append({"text": rest[position : match.start()]})
        href = link(address)
        spans.append({"text": address, "href": href} if href else {"text": address})
        position = match.start() + len(address)
    if position < len(rest):
        spans.append({"text": rest[position:]})
    return spans


def _address(found: str) -> str:
    """The address without the punctuation after it. A closing bracket stays
    when it closes one in the address (wiki/Modbus_(protocol))."""
    while found and found[-1] in _URL_TAIL:
        if found[-1] == ")" and found.count("(") >= found.count(")"):
            break
        found = found[:-1]
    return found


# Cleaning up


def _without_title(blocks: list[Block], title: str) -> list[Block]:
    """The blocks without the headline: the reader shows it above them."""
    for index, block in enumerate(blocks[:LEAD_WITHIN]):
        if block["type"] == "h":
            text = block["text"]
        elif block["type"] == "p":
            text = _joined(block["spans"])
        else:
            continue
        return [*blocks[:index], *blocks[index + 1 :]] if _key(text) == title else blocks
    return blocks


def _without_empty_sections(blocks: list[Block]) -> list[Block]:
    """Headings with nothing under them: a table of contents the page drew
    with links, a section that was all pictures the page did not give."""
    kept: list[Block] = []
    following: Block | None = None
    # From the end, so that a section whose only subsection was empty goes too.
    for block in reversed(blocks):
        if block["type"] == "h" and (
            following is None or (following["type"] == "h" and following["level"] <= block["level"])
        ):
            continue
        kept.append(block)
        following = block
    return kept[::-1]


def _plain(element: _Element) -> str:
    return " ".join("".join(element.itertext()).split())


def _joined(spans: Iterable[Span]) -> str:
    return "".join(span["text"] for span in spans)


def _size(spans: Iterable[Span]) -> int:
    return sum(len(span["text"]) for span in spans)


def _block_size(block: Block) -> int:
    """Characters of text in the block; a picture has none."""
    if block["type"] == "p" or block["type"] == "quote":
        return _size(block["spans"])
    if block["type"] == "list":
        return sum(_size(item) for item in block["items"])
    if block["type"] == "h" or block["type"] == "code":
        return len(block["text"])
    if block["type"] == "table":
        return sum(len(cell) for row in block["rows"] for cell in row)
    return 0


def _key(text: str) -> str:
    return "".join(char for char in text.casefold() if char.isalnum())
