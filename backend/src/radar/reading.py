"""How long an article takes to read.

Counted from the full text only: most feeds carry a teaser, and a minute
estimated from a teaser would be a lie. Speeds are those of silent reading
of non-fiction: about 180 words a minute in Russian, 220 in English.
"""

import math
import re

_WORD_RE = re.compile(r"[^\W_]+(?:[-'’][^\W_]+)*")
WORDS_PER_MINUTE = {"ru": 180, "en": 220}
DEFAULT_WORDS_PER_MINUTE = 200
# Fewer words than this is a teaser or a stub, not an article to time.
MIN_WORDS = 80


def word_count(text: str | None) -> int | None:
    """Words of a full text; None when there is no text worth timing."""
    if not text:
        return None
    count = len(_WORD_RE.findall(text))
    return count if count >= MIN_WORDS else None


def reading_minutes(words: int | None, language: str) -> int | None:
    """Whole minutes, rounded up; None when the length is unknown."""
    if not words:
        return None
    speed = WORDS_PER_MINUTE.get(language, DEFAULT_WORDS_PER_MINUTE)
    return max(1, math.ceil(words / speed))
