"""What a short video is made of: the script, the narration and the timeline."""

import re
from dataclasses import dataclass
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
ACTIVE_STATUSES = (STATUS_QUEUED, STATUS_RUNNING)

STAGE_SCRIPT = "script"
STAGE_VOICE = "voice"
STAGE_RENDER = "render"

# Limits of the renderer's props schema (shorts/src/schema.ts). Text is cut
# to them here, so a long headline shortens the card instead of failing the
# render.
MAX_KICKER = 40
MAX_TITLE = 140
MAX_FACT = 32
MAX_SOURCE = 60
MAX_LINE = 120
MAX_AUDIENCE = 40
MAX_WORD = 40
MAX_WORDS = 800
MAX_DURATION_MS = 120_000
# What is spoken over one news card: two sentences at most.
MAX_NARRATION = 280
MAX_POINT = 60
MAX_POINTS = 3
MAX_URL = 200
MAX_DATE = 24

# What a news item is about; picks the picture and colour of its card.
Visual = Literal[
    "vulnerability", "attack", "incident", "regulation", "release", "research", "energy", "other"
]
VISUALS: tuple[Visual, ...] = get_args(Visual)
_URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)


class ShortError(Exception):
    """The video cannot be made. The message is written for the reader."""


def _has_words(value: str) -> str:
    # A line of punctuation alone would be silence in the voice and nothing
    # in the captions, and the renderer refuses empty strings.
    if not any(char.isalnum() for char in value):
        raise ValueError("the line has no words")
    return value


# Whitespace is stripped and every line must say something: an empty string
# here would only fail later, in the renderer, without a fallback.
_STRICT = ConfigDict(frozen=True, str_strip_whitespace=True, str_min_length=1)


class Beat(BaseModel):
    """One news item of the video."""

    model_config = _STRICT

    article_id: int
    kicker: str = Field(max_length=MAX_KICKER)
    title: str = Field(max_length=MAX_TITLE)
    fact: str | None = Field(default=None, max_length=MAX_FACT)
    narration: str = Field(max_length=MAX_NARRATION)
    source: str = Field(max_length=MAX_SOURCE)
    visual: Visual = "other"
    # Short facts ticked off on screen while the item is told.
    points: tuple[str, ...] = Field(default=(), max_length=MAX_POINTS)
    # The article, for the QR code on the card.
    url: str | None = Field(default=None, max_length=MAX_URL)
    # When it was published, e.g. "29 сентября".
    date: str | None = Field(default=None, max_length=MAX_DATE)

    _spoken = field_validator("kicker", "title", "narration", "source")(_has_words)

    @field_validator("points")
    @classmethod
    def _short_points(cls, points: tuple[str, ...]) -> tuple[str, ...]:
        for point in points:
            _has_words(point)
            if len(point) > MAX_POINT:
                raise ValueError(f"a point is longer than {MAX_POINT} characters")
        return points

    @field_validator("url")
    @classmethod
    def _web_address(cls, url: str | None) -> str | None:
        # A code that opens anything but a web page has no place on the card.
        if url is not None and not _URL_RE.match(url):
            raise ValueError("the source address must be http or https")
        return url


class Script(BaseModel):
    model_config = _STRICT

    hook: str = Field(max_length=MAX_LINE)
    beats: tuple[Beat, ...] = Field(min_length=1, max_length=7)
    outro: str = Field(max_length=MAX_LINE)
    # False when the offline writer produced it.
    by_model: bool = False

    _spoken = field_validator("hook", "outro")(_has_words)

    def lines(self) -> list[str]:
        """Everything that is said, in order: the hook, each item, the outro."""
        return [self.hook, *(beat.narration for beat in self.beats), self.outro]


@dataclass(frozen=True, slots=True)
class Segment:
    """Where one spoken line sits in the narration, in milliseconds."""

    start_ms: int
    end_ms: int


@dataclass(frozen=True, slots=True)
class Narration:
    """The voice track, or its timing alone when the video is silent."""

    segments: tuple[Segment, ...]
    # WAV bytes; None for a silent video.
    audio: bytes | None
    voice: str | None
