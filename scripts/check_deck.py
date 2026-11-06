"""Check that every number on a slide stands in the documents the slide cites.

    python scripts/check_deck.py docs/presentation/slides.html

Each slide names where its numbers come from in its footer: paths such as
docs/BUSINESS.md or examples/vs-analyst. Every number of the slide, outside
the footer, has to be found in one of those files (a folder means every file
in it), or in docs/QUALITY.md and README.md, which hold the measurements
the deck is built on. Numbers are compared as written in Russian text: thin
and non-breaking spaces between thousands are dropped, so "1 737" in a slide
matches "1737" or "1 737" in a document, and a rounded number matches the
exact one it rounds ("97%" on a slide, "96,8%" in QUALITY.md). Slide numbers
("05 / 14"), years, clock times, law numbers ("152-ФЗ"), footnote marks and
numbers below 10 are skipped: they say nothing that could go stale.

One line per number not found, "slide N: number - context". The exit code is
1 when there is any, so the deck cannot drift from the documents unnoticed.
"""

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALWAYS = ("docs/QUALITY.md", "README.md")
_PATH_RE = re.compile(r"(?:docs|examples|backend|scripts)/[\w./-]+")
_NUMBER_RE = re.compile(r"(?<![\w.,])\d{1,3}(?:[   ]\d{3})+(?:,\d+)?|(?<![\w.,])\d+(?:,\d+)?")
_GROUP_RE = re.compile(r"(?<=\d)[   ](?=\d{3}\b)")
_PAGE_RE = re.compile(r"\b\d{2} / \d{2}\b")
_DECIMAL_DOT_RE = re.compile(r"(?<=\d)\.(?=\d)")
_SKIP_RE = re.compile(r"\b\d{1,2}:\d{2}\b|\b\d+-ФЗ\b")
_VOID = {"img", "br", "hr", "input", "meta", "link", "source", "wbr"}


class _Slides(HTMLParser):
    """The text of each slide, its footer source apart."""

    def __init__(self) -> None:
        super().__init__()
        self.slides: list[tuple[str, str]] = []
        self._depth = 0
        self._in_src = 0
        self._in_ref = 0
        self._text: list[str] = []
        self._src: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = (dict(attrs).get("class") or "").split()
        if tag == "section" and "slide" in classes:
            self._depth, self._text, self._src = 1, [], []
            return
        if not self._depth or tag in _VOID:
            return
        self._depth += 1
        if "src" in classes or self._in_src:
            self._in_src += 1
        if "ref" in classes or self._in_ref:
            self._in_ref += 1

    def handle_endtag(self, tag: str) -> None:
        if not self._depth:
            return
        if self._in_src:
            self._in_src -= 1
        if self._in_ref:
            self._in_ref -= 1
        self._depth -= 1
        if not self._depth:
            self.slides.append((" ".join(self._text), " ".join(self._src)))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        pass

    def handle_data(self, data: str) -> None:
        if self._in_ref:
            self._text.append(" | ")
        elif self._depth:
            (self._src if self._in_src else self._text).append(data)


def normalize(text: str) -> str:
    return _GROUP_RE.sub("", text)


def value_of(number: str) -> float:
    return float(number.replace(",", "."))


def corpus(source: str) -> str:
    texts = []
    for name in (*_PATH_RE.findall(source), *ALWAYS):
        path = ROOT / name.rstrip(".,;")
        files = sorted(path.rglob("*")) if path.is_dir() else [path]
        for file in files:
            if file.is_file() and file.suffix in {".md", ".json", ".py", ".js", ".csv"}:
                texts.append(file.read_text(encoding="utf-8", errors="replace"))
    # The documents write a decimal either way: "0.95" in a table, "0,95" in text.
    return _DECIMAL_DOT_RE.sub(",", normalize("\n".join(texts)))


def numbers(text: str) -> list[tuple[str, str]]:
    text = _SKIP_RE.sub(" ", _PAGE_RE.sub(" ", text))
    found = []
    for match in _NUMBER_RE.finditer(text):
        value = normalize(match.group())
        digits = value.replace(",", "")
        if len(digits) < 2 or (len(value) == 4 and value.startswith("20")):
            continue
        context = text[max(match.start() - 30, 0) : match.end() + 30]
        found.append((value, " ".join(context.split())))
    return found


def check(deck: Path) -> list[str]:
    parser = _Slides()
    parser.feed(deck.read_text(encoding="utf-8"))
    problems = []
    for index, (text, source) in enumerate(parser.slides, start=1):
        known = {value_of(number) for number, _ in numbers(corpus(source))}
        for value, context in numbers(text):
            decimals = len(value.partition(",")[2])
            half = 0.5 * 10**-decimals
            if not any(abs(number - value_of(value)) <= half for number in known):
                problems.append(f"slide {index}: {value} - {context}")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("deck", type=Path)
    problems = check(parser.parse_args().deck)
    sys.stdout.write(("\n".join(problems) or "every number of the deck is in its documents") + "\n")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
