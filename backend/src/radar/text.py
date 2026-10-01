"""Text and URL normalisation used by ingestion, dedup and the offline models."""

import hashlib
import html
import re
from urllib.parse import parse_qsl, unquote_plus, urlencode, urlsplit, urlunsplit

_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_SPACE_RE = re.compile(r"\s+")
# Hyphenated compounds split into parts ("SCADA-система" must match "SCADA");
# a trailing + or # is kept for names like C++ and C#.
_WORD_RE = re.compile(r"[a-zа-яё0-9]+[+#]*", re.IGNORECASE)
_SENTENCE_RE = re.compile(r"(?<=[.!?…])\s+(?=[A-ZА-ЯЁ0-9«\"])")
_TRACKING_PREFIXES = ("utm_", "yclid", "gclid", "fbclid", "mc_", "ref_", "_openstat")
_TRACKING_KEYS = frozenset({"from", "ref", "spm", "cmpid", "rss"})

# Function words carry no topical signal; the list is deliberately short and
# covers both languages the sources are written in.
STOPWORDS = frozenset(
    """
    и в во не что он на я с со как а то все она так его но да ты к у же вы за бы по только
    ее мне было вот от меня еще нет о из ему теперь когда даже ну вдруг ли если уже или ни
    быть был него до вас нибудь опять уж вам ведь там потом себя ничего ей может они тут где
    есть надо ней для мы тебя их чем была сам чтоб без будто чего раз тоже себе под будет ж
    тогда кто этот того потому этого какой совсем ним здесь этом один почти мой тем чтобы
    нее сейчас были куда зачем всех никогда можно при наконец два об другой хоть после над
    больше тот через эти нас про всего них какая много разве три эту моя впрочем хорошо свою
    этой перед иногда лучше чуть том нельзя такой им более всегда конечно всю между это
    также которые который которая которых году года лет новый новая новые новых стал стала
    стали будут могут свой свои своих её наш
    the a an and or of to in on for with by from at as is are was were be been it its this
    that these those has have had will would can could not no but if than then so into over
    about after new how what why who when where which their they we you your our more most
    via using use
    """.split()  # noqa: SIM905
)


def strip_html(raw: str) -> str:
    """Reduce an HTML fragment to plain text with single spaces."""
    without_scripts = _SCRIPT_RE.sub(" ", raw)
    text = html.unescape(_TAG_RE.sub(" ", without_scripts))
    return _SPACE_RE.sub(" ", text.replace("\xa0", " ")).strip()


def _is_tracking(key: str) -> bool:
    key = key.lower()
    return key.startswith(_TRACKING_PREFIXES) or key in _TRACKING_KEYS


def canonical_url(url: str) -> str:
    """Drop fragments and tracking parameters so reposts collapse to one URL."""
    parts = urlsplit(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=False)
        if not _is_tracking(key)
    ]
    path = parts.path.rstrip("/") or "/"
    host = parts.netloc.lower().removeprefix("www.")
    return urlunsplit((parts.scheme.lower(), host, path, urlencode(query), ""))


def untracked_url(url: str) -> str:
    """The same page without tracking parameters and credentials: an address
    to open, not a key to compare.

    The rest of the query is kept byte for byte, so a value in cp1251 or a
    bare flag like "?print" still opens the page it opened before. A fragment
    is dropped unless it is a route of a single-page site ("#/news/1", "#!").
    """
    parts = urlsplit(url.strip())
    query = "&".join(
        pair
        for pair in parts.query.split("&")
        if pair and not _is_tracking(unquote_plus(pair.split("=", 1)[0]))
    )
    host = parts.netloc.rpartition("@")[2]
    fragment = parts.fragment if parts.fragment.startswith(("/", "!")) else ""
    return urlunsplit((parts.scheme, host, parts.path, query, fragment))


def tokenize(text: str) -> list[str]:
    return [match.group(0).lower().replace("ё", "е") for match in _WORD_RE.finditer(text)]


def content_tokens(text: str) -> list[str]:
    """Tokens without stopwords and one-letter noise."""
    return [tok for tok in tokenize(text) if len(tok) > 1 and tok not in STOPWORDS]


def content_hash(title: str, body: str) -> str:
    """Stable fingerprint of what the article says, independent of markup."""
    normalized = " ".join(tokenize(f"{title} {body}"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_RE.split(text) if part.strip()]


def truncate(text: str, limit: int) -> str:
    """Cut on a word boundary and mark the cut."""
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:-")
    return f"{cut}…"


def detect_language(text: str) -> str:
    """Cheap script-based guess; enough to pick between Russian and English."""
    cyrillic = sum(1 for ch in text if "а" <= ch.lower() <= "я" or ch in "ёЁ")
    latin = sum(1 for ch in text if "a" <= ch.lower() <= "z")
    return "ru" if cyrillic >= latin else "en"


def stable_hash(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:32]
