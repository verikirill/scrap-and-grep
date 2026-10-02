"""Text of a short as it is shown and as it is spoken."""

import re

from radar.text import numbers, truncate

# Quotes, brackets and markup are not spoken, and some voices read them out.
_UNSPOKEN_RE = re.compile(r"[«»\"“”„()\[\]{}*_#<>|~^`]")
_LINK_RE = re.compile(r"https?://|www\.|\b[\w.-]+\.(?:ru|com|org|net|io|рф)\b", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE_RE = re.compile(r"(?:\+?\d[\s()-]*){10,}")
# "CVE-2026-1234567" has as many digits as a phone number.
_CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)


def clean(text: str, limit: int, fallback: str) -> str:
    """One line of screen text: single spaces, cut to the limit, and the
    fallback when nothing readable is left."""
    line = " ".join(text.split())
    if not any(char.isalnum() for char in line):
        return fallback
    return truncate(line, limit - 1)


def spoken(text: str) -> str:
    """The line as it should be read aloud and shown in captions."""
    return " ".join(_UNSPOKEN_RE.sub("", text).split())


def is_grounded(text: str, allowed: set[str]) -> bool:
    """Text a model wrote can go on air: no links, addresses or phone numbers,
    and no figure that is not in `allowed`.

    Feed text reaches the model, and a hostile article may try to make the
    video read out a phone number or a link. Such lines are replaced by the
    digest's own text.
    """
    if _LINK_RE.search(text) or _EMAIL_RE.search(text):
        return False
    if _PHONE_RE.search(_CVE_RE.sub(" ", text)):
        return False
    return numbers(text) <= allowed
