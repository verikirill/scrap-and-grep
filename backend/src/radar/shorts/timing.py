"""The timeline of a short: when each word is said and each card is shown.

The voice service reports where every line starts and ends. Inside a line,
time is shared out by syllables, the unit speech length follows most
closely, with a little extra after commas and full stops. Captions show a
page of two to four words, so an error of a syllable or two is not visible.
"""

from datetime import UTC, datetime
from itertools import pairwise
from typing import Any
from zoneinfo import ZoneInfo

from radar.shorts.model import (
    MAX_AUDIENCE,
    MAX_DURATION_MS,
    MAX_WORD,
    MAX_WORDS,
    Narration,
    Script,
    Segment,
    ShortError,
)
from radar.shorts.speech import clean

BRAND = "Радар"
# Dates are shown on the calendar the interface uses.
MOSCOW = ZoneInfo("Europe/Moscow")
_VOWELS = frozenset("аеёиоуыэюяaeiouy")
# Digits are read as words: "2026" is eight syllables, about two per digit.
_SYLLABLES_PER_DIGIT = 2.0
# Pauses in syllables, after the punctuation that causes them.
_PAUSES = ((("...", "…", ".", "!", "?"), 1.2), ((":", ";"), 0.9), ((",",), 0.6))
_DASH_PAUSE = 0.5
_TRIM = "«»\"'()[]{},.;:!?…"
# The renderer adds its own tail after the last word (shorts/src/Root.tsx).
_RENDER_TAIL_MS = 700
_END_PAD_MS = 200
# The longest narration the renderer takes, with both tails.
SILENT_BUDGET_MS = MAX_DURATION_MS - _RENDER_TAIL_MS - _END_PAD_MS

# A silent video is read, not heard: slower than speech.
SILENT_MS_PER_SYLLABLE = 230
SILENT_GAP_MS = 450
SILENT_START_MS = 300
_SILENT_MIN_LINE_MS = 1200
# Qwen3-TTS with the Aiden voice spoke at 182-188 ms a syllable, pauses at
# the edges of lines included; a silent video is never read faster than that.
_SILENT_MIN_PACE = 0.8

_MONTHS = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


def syllables(word: str) -> float:
    """Rough length of a word when read aloud."""
    letters = [char for char in word.lower() if char.isalnum()]
    digits = sum(char.isdigit() for char in letters)
    vowels = sum(char in _VOWELS for char in letters)
    # Abbreviations are spelled out letter by letter: "КИИ", "ФСТЭК", "CVE".
    if word.strip(_TRIM).isupper() and 2 <= len(letters) <= 6 and vowels <= 2 and not digits:
        return float(len(letters))
    return max(1.0, vowels + digits * _SYLLABLES_PER_DIGIT)


def _pause_after(token: str) -> float:
    for endings, pause in _PAUSES:
        if token.endswith(endings):
            return pause
    return 0.0


def _units(text: str) -> list[tuple[str | None, float]]:
    """Words with their weights, and pauses as weights without a word."""
    units: list[tuple[str | None, float]] = []
    for token in text.split():
        if not any(char.isalnum() for char in token):
            units.append((None, _DASH_PAUSE))
            continue
        units.append((token, syllables(token)))
        pause = _pause_after(token)
        if pause:
            units.append((None, pause))
    # Silence at the end of a line belongs to the gap before the next one.
    while units and units[-1][0] is None:
        units.pop()
    return units


def line_weight(text: str) -> float:
    return sum(weight for _, weight in _units(text))


def time_words(text: str, segment: Segment) -> list[dict[str, Any]]:
    """Words of one line with their start and end, spread over its segment."""
    units = _units(text)
    total = sum(weight for _, weight in units)
    if not units or total <= 0:
        return []
    span = segment.end_ms - segment.start_ms
    words = []
    at = float(segment.start_ms)
    for word, weight in units:
        length = span * weight / total
        caption = word.strip(_TRIM) if word else ""
        if caption:
            words.append(
                {
                    "text": caption[:MAX_WORD],
                    "startMs": round(at),
                    "endMs": round(at + length),
                }
            )
        at += length
    return words


def estimate_segments(lines: list[str]) -> tuple[Segment, ...]:
    """Timing for a video without a voice, at a comfortable reading pace.

    A script that fits in voice may not fit at reading pace; then the pace is
    raised, up to speech speed, rather than the video refused.
    """
    natural = [
        max(_SILENT_MIN_LINE_MS, line_weight(line) * SILENT_MS_PER_SYLLABLE) for line in lines
    ]
    budget = SILENT_BUDGET_MS - SILENT_START_MS - SILENT_GAP_MS * (len(lines) - 1)
    pace = max(_SILENT_MIN_PACE, min(1.0, budget / sum(natural))) if natural else 1.0
    segments = []
    at = SILENT_START_MS
    for length in natural:
        segment = Segment(at, at + round(length * pace))
        segments.append(segment)
        at = segment.end_ms + SILENT_GAP_MS
    return tuple(segments)


def _moscow(moment: datetime) -> datetime:
    # The database keeps UTC; a naive value would otherwise be read in the
    # server's own time zone.
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(MOSCOW)


def format_day(moment: datetime) -> str:
    """ "29 сентября", on the Moscow calendar the interface uses."""
    local = _moscow(moment)
    return f"{local.day} {_MONTHS[local.month - 1]}"


def format_period(start: datetime, end: datetime) -> str:
    """ "23-30 сентября" or "28 сентября - 5 октября"."""
    start, end = _moscow(start), _moscow(end)
    if (start.year, start.month) == (end.year, end.month):
        if start.day == end.day:
            return f"{end.day} {_MONTHS[end.month - 1]}"
        return f"{start.day}-{end.day} {_MONTHS[end.month - 1]}"
    return f"{start.day} {_MONTHS[start.month - 1]} - {end.day} {_MONTHS[end.month - 1]}"


def build_props(
    script: Script, narration: Narration, *, period: str, audience: str
) -> dict[str, Any]:
    """The renderer's input (shorts/src/schema.ts), without the audio address."""
    lines = script.lines()
    segments = narration.segments
    if len(segments) != len(lines):
        raise ValueError(f"{len(segments)} narration segments for {len(lines)} lines")
    words = [
        word
        for line, segment in zip(lines, segments, strict=True)
        for word in time_words(line, segment)
    ]
    duration = segments[-1].end_ms + _END_PAD_MS
    if duration + _RENDER_TAIL_MS > MAX_DURATION_MS or len(words) > MAX_WORDS:
        raise ShortError("Сценарий получился длиннее двух минут. Попробуйте выпуск покороче.")
    # Cards change halfway through the pause between lines, so a picture
    # never runs ahead of the voice.
    cuts = [(current.end_ms + following.start_ms) // 2 for current, following in pairwise(segments)]
    beats = [
        {
            "kicker": beat.kicker,
            "title": beat.title,
            "fact": beat.fact,
            "visual": beat.visual,
            "points": list(beat.points),
            "source": beat.source,
            "url": beat.url,
            "date": beat.date,
            "startMs": cuts[index],
            "endMs": max(cuts[index + 1], cuts[index] + 1),
        }
        for index, beat in enumerate(script.beats)
    ]
    return {
        "brand": BRAND,
        "period": period,
        "audience": clean(audience, MAX_AUDIENCE, BRAND),
        "hook": script.hook,
        "hookEndMs": cuts[0],
        "beats": beats,
        "outro": script.outro,
        "outroStartMs": cuts[-1],
        "words": words,
        "durationMs": duration,
    }
