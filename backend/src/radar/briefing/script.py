"""The script of a spoken brief for management: plain words, two minutes at most.

The brief retells a management digest, which the model has already written in
plain words for this reader: its title, what the period means for the company,
the highlights and the strongest entries. Nothing is written anew, so nothing
new can be invented on air, and no feed text reaches a model on the way. What
a listener cannot take in by ear (CVE and BDU numbers, CVSS scores and
vectors, addresses, hashes, links) is taken out of every line.
"""

import re
from collections.abc import Sequence

from pydantic import BaseModel

from radar.shorts.script import pick_items
from radar.shorts.speech import spoken
from radar.shorts.timing import format_period, line_weight
from radar.shorts.voice import GAP_MS
from radar.text import truncate
from radar.views import DigestView, ItemView

# Two minutes at most, judged by syllables at the pace of the voice.
MAX_MS = 120_000
MS_PER_SYLLABLE = 190
# The voice service reads a sentence of 400 characters at most; a line goes
# to it as one sentence, after quotes and brackets are dropped.
MAX_LINE = 380
MAX_ENTRIES = 5

INTRO = "Брифинг Tail and Grep для руководства"
IMPLICATIONS_LABEL = "Что это значит для нас."
HIGHLIGHTS_LABEL = "Главное."
ENTRIES_LABEL = "Подробнее о главных событиях."
OUTRO = "Полный выпуск со ссылками ждёт в Tail and Grep."
NO_ENTRIES = "В выпуске нет записей, брифингу не о чем рассказать."

# How much of the digest is told, from the fullest brief down: what it means
# for the company, the highlights, the entries and whether an entry gets a
# sentence beyond its headline. The first one that fits two minutes is read.
_STEPS = (
    (3, 3, 5, True),
    (3, 3, 4, True),
    (3, 2, 4, True),
    (3, 2, 3, True),
    (2, 2, 3, True),
    (2, 1, 3, True),
    (1, 1, 3, True),
    (1, 1, 3, False),
)

_LINK = r"\b(?:https?|hxxps?|ftp)://[^\s()<>«»\"']*[^\s()<>«»\"'.,;:!?]"
_EMAIL = r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"
_DOMAIN = r"\b(?:[\w-]+(?:\[\.\]|\.))+(?:ru|com|org|net|io|info|biz|gov|edu|su|onion|рф)\b"
_CVSS_PHRASE = r"\b\d{1,2}(?:[.,]\d)?\s+(?:балл\w*\s+)?по\s+(?:шкале\s+)?CVSS(?:\s*v?\d\.\d)?"
_CVSS = (
    r"\bCVSS(?:[:\s]*v?(?:2\.0|3\.[01]|4\.0)(?!\d))?(?:/[A-Z]{1,3}:[A-Z])*"
    r"(?:[\s:]*(?:base\s+score\s*)?(?:10(?:[.,]0)?|\d(?:[.,]\d)?)(?!\d|[.,]\d))?"
)
_VECTOR = r"\bAV:[NALP](?:/[A-Z]{1,3}:[A-Z])+"
_IDS = r"\bCVE-\d{4}-\d{4,7}\b|\b(?:BDU|БДУ)\s*:?\s*\d{4}-\d{5}\b|\bCWE-\d+\b"
_TECHNIQUE = r"\bT\d{4}(?:\.\d{3})?\b"
_IPV6 = (
    r"(?<![\w:])(?:[0-9a-f]{1,4}:){1,7}(?::[0-9a-f]{1,4}){1,7}(?![\w:])"
    r"|(?<![\w:])(?:[0-9a-f]{1,4}:){7}[0-9a-f]{1,4}(?![\w:])"
)
_DOT = r"(?:\[\.\]|\.)"
_IPV4 = rf"\b\d{{1,3}}{_DOT}\d{{1,3}}{_DOT}\d{{1,3}}{_DOT}\d{{1,3}}(?::\d{{1,5}})?\b"
_HASH = r"\b[0-9a-f]{32,128}\b"
# Links first: a domain inside a link must not leave the rest of it behind.
_TECHNICAL = re.compile(
    "|".join(
        f"(?:{pattern})"
        for pattern in (
            _LINK,
            _EMAIL,
            _DOMAIN,
            _CVSS_PHRASE,
            _CVSS,
            _VECTOR,
            _IDS,
            _TECHNIQUE,
            _IPV6,
            _IPV4,
            _HASH,
        )
    ),
    re.IGNORECASE,
)
# What a removed mark leaves behind: "шлюзы (), это", "патч, .", "( , x)".
_EMPTY_BRACKETS = re.compile(r"[(\[][\s,;:]*[)\]]")
_OPEN_SEPARATOR = re.compile(r"([(\[])[\s,;:]+")
_SEPARATOR_CLOSE = re.compile(r"[\s,;:]+([)\]])")
_SPACE_BEFORE = re.compile(r"\s+([,.;:!?…)\]])")
_REPEATED = re.compile(r"([,;:])(?:\s*[,;:])+")
_BEFORE_END = re.compile(r"[,;:]+(?=[.!?…])")
_LEADING = re.compile(r"^[\s,;:.!?-]+")
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


class BriefingError(Exception):
    """The brief cannot be made. The message is written for the reader."""


class BriefingScript(BaseModel):
    lines: list[str]
    # How many entries of the digest the brief tells.
    entries: int
    estimated_ms: int


def plain(text: str) -> str:
    """The text without the marks a listener cannot take in by ear."""
    text = _TECHNICAL.sub("", text)
    text = _EMPTY_BRACKETS.sub("", text)
    text = _OPEN_SEPARATOR.sub(r"\1", text)
    text = _SEPARATOR_CLOSE.sub(r"\1", text)
    text = _SPACE_BEFORE.sub(r"\1", text)
    text = _REPEATED.sub(r"\1", text)
    text = _BEFORE_END.sub("", text)
    return _LEADING.sub("", " ".join(text.split()))


def estimate_ms(lines: Sequence[str]) -> int:
    """How long the lines take to say, with the pause between them."""
    if not lines:
        return 0
    syllables = sum(line_weight(spoken(line)) for line in lines)
    return round(syllables * MS_PER_SYLLABLE) + GAP_MS * (len(lines) - 1)


def _sentence(text: str) -> str:
    text = text.strip()
    return text if text.endswith((".", "!", "?", "…")) else f"{text}."


def _first_sentence(text: str) -> str:
    parts = _SENTENCE_END.split(plain(text), maxsplit=1)
    return _sentence(parts[0]) if parts[0] else ""


def _fit(text: str, limit: int) -> str:
    """Whole sentences up to the limit; a first sentence too long is cut on a word."""
    fitted = ""
    for sentence in _SENTENCE_END.split(text):
        longer = f"{fitted} {sentence}".strip()
        if len(longer) > limit:
            break
        fitted = longer
    return fitted or truncate(text, limit - 1)


def _said(texts: Sequence[str]) -> list[str]:
    """Lines of the digest that still say something once the marks are out."""
    cleaned = (plain(text) for text in texts)
    return [_sentence(text) for text in cleaned if any(char.isalpha() for char in text)]


def _entry(item: ItemView) -> tuple[str, str]:
    """An entry as its headline and one sentence on what it means; the summary
    speaks for an entry that has nothing on the company."""
    return _sentence(plain(item.headline)), _first_sentence(item.why or item.summary)


def _section(label: str, texts: Sequence[str]) -> list[str]:
    lines = [_fit(text, MAX_LINE) for text in texts]
    if lines:
        lines[0] = f"{label} {_fit(texts[0], MAX_LINE - len(label) - 1)}"
    return lines


def build_script(view: DigestView) -> BriefingScript:
    """Retell a management digest in about two minutes of plain speech."""
    entries = [_entry(item) for item in pick_items(view, MAX_ENTRIES)]
    if not entries:
        raise BriefingError(NO_ENTRIES)
    intro = f"{INTRO}, {format_period(view.period_start, view.period_end)}."
    title = plain(view.title or "")
    if any(char.isalpha() for char in title):
        intro = f"{intro} {_sentence(title)}"
    implications = _said(view.implications)
    highlights = _said(view.highlights)

    def compose(risks: int, main: int, told: int, detail: bool) -> list[str]:
        stories = [f"{head} {more}" if detail and more else head for head, more in entries[:told]]
        return [
            _fit(intro, MAX_LINE),
            *_section(IMPLICATIONS_LABEL, implications[:risks]),
            *_section(HIGHLIGHTS_LABEL, highlights[:main]),
            *_section(ENTRIES_LABEL, stories),
            OUTRO,
        ]

    for risks, main, told, detail in _STEPS:
        lines = compose(risks, main, told, detail)
        if estimate_ms(lines) <= MAX_MS:
            break
    # Lines too long for any step are shortened, the longest first.
    while estimate_ms(lines) > MAX_MS:
        longest = max(range(len(lines)), key=lambda index: len(lines[index]))
        lines[longest] = truncate(lines[longest], len(lines[longest]) * 4 // 5)
    return BriefingScript(
        lines=lines, entries=min(told, len(entries)), estimated_ms=estimate_ms(lines)
    )
