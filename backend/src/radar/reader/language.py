"""The language an article is written in, told by its letters.

The source's language is only a hint: an English blog in a Russian catalogue
and a Chinese vendor's bulletin come through feeds marked "ru" or "auto".
"""

import re
from collections.abc import Iterable
from typing import Literal

from radar.reader.blocks import Block, plain_text

type Language = Literal["ru", "en", "zh", "other"]

# Enough text to tell a language; the rest of a long article adds nothing.
SAMPLE_CHARS = 5000
# Russian IT news is full of Latin names (Microsoft, Exchange, CVE): a third
# of Cyrillic letters is a Russian text, an English one quotes a phrase at most.
_CYRILLIC_SHARE = 0.3
# Chinese bulletins name products in Latin letters; a Han character is a
# word or half of one, so a small share of them is already the text.
_HAN_SHARE = 0.15
# Kana among the CJK characters is Japanese, not Chinese.
_KANA_SHARE = 0.2
# Function words make up a third of English prose; a German or French text
# has almost none of these.
_ENGLISH_SHARE = 0.08
# Fewer Latin words than this cannot tell English from another language:
# a headline of names is taken for English, the most common case by far.
_FEW_WORDS = 30
_ENGLISH_WORDS = frozenset((
    "the", "a", "an", "of", "to", "in", "and", "or", "is", "are", "was", "were", "be",
    "been", "for", "on", "with", "by", "at", "from", "as", "that", "this", "it", "its",
    "which", "who", "has", "have", "had", "not", "but", "can", "will", "would", "should",
    "may", "also", "than", "these", "those", "into", "after", "before", "about", "over",
    "more", "new", "could", "their", "they", "there",
))  # fmt: skip
_LATIN_WORD = re.compile(r"[a-z]+")


def _counts(text: str) -> tuple[int, int, int, int, int]:
    cyrillic = latin = han = kana = hangul = 0
    for char in text:
        code = ord(char)
        if "a" <= char.lower() <= "z":
            latin += 1
        elif 0x0400 <= code <= 0x04FF:
            cyrillic += 1
        elif 0x4E00 <= code <= 0x9FFF or 0x3400 <= code <= 0x4DBF:
            han += 1
        elif 0x3040 <= code <= 0x30FF:
            kana += 1
        elif 0xAC00 <= code <= 0xD7AF:
            hangul += 1
    return cyrillic, latin, han, kana, hangul


def _latin(text: str, hint: str | None) -> Language:
    words = _LATIN_WORD.findall(text.lower())
    common = sum(word in _ENGLISH_WORDS for word in words)
    if words and common / len(words) >= _ENGLISH_SHARE:
        return "en"
    if hint == "en" or len(words) < _FEW_WORDS:
        return "en"
    return "other"


def detect(text: str, hint: str | None = None) -> Language:
    """ru, en, zh, or other for a text in a language the reader does not translate."""
    cyrillic, latin, han, kana, hangul = _counts(text[:SAMPLE_CHARS])
    letters = cyrillic + latin + han + kana + hangul
    if not letters:
        return "ru"
    eastern = han + kana + hangul
    if eastern / letters >= _HAN_SHARE:
        is_chinese = kana < _KANA_SHARE * eastern and hangul < _KANA_SHARE * eastern
        return "zh" if is_chinese else "other"
    if cyrillic / (cyrillic + latin or 1) >= _CYRILLIC_SHARE:
        return "ru"
    return _latin(text[:SAMPLE_CHARS], hint)


def article_language(title: str, blocks: Iterable[Block], hint: str | None = None) -> Language:
    """The language of an article's headline and prose; code and tables are left out."""
    return detect(f"{title}\n{plain_text(blocks)}", hint)
