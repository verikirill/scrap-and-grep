"""What a channel posts, how it sounds and when: kept as one JSON document so
that new knobs do not need a migration."""

import re
from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo, available_timezones

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_PAIR = r"[A-Za-z0-9_.~\-]+=[A-Za-z0-9_.~%\-]*"
_UTM_RE = re.compile(rf"{_PAIR}(&{_PAIR})*")
DEFAULT_TIMEZONE = "Europe/Moscow"
MAX_SLOTS = 48

TonePreset = Literal["punchy", "neutral", "expert", "custom"]
LinkMode = Literal["none", "inline", "preview", "button"]
PostFormat = Literal["classic", "rich"]
MediaMode = Literal["auto", "none"]
Approval = Literal["auto", "manual"]
NetworkPolicy = Literal["share", "spread"]


def _clock(value: str) -> str:
    value = value.strip()
    if not _TIME_RE.match(value):
        raise ValueError(f"time must look like 09:30, got {value!r}")
    return value


@lru_cache(maxsize=1)
def _zones() -> frozenset[str]:
    return frozenset(available_timezones())


def minutes_of(clock: str) -> int:
    hours, minutes = clock.split(":")
    return int(hours) * 60 + int(minutes)


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")


class Style(_Frozen):
    """How the posts sound. The audience defaults to the role of the profile."""

    tone: TonePreset = "punchy"
    # Free instructions on top of the preset, e.g. "без жаргона, на вы".
    instructions: str = Field(default="", max_length=1000)
    audience: str = Field(default="", max_length=600)
    # A plain emoji before the first sentence; custom emoji are paid and not used.
    emoji: str = Field(default="⚡", max_length=8)
    length: Literal["short", "medium", "long"] = "medium"
    bullets: bool = True
    ending: bool = True
    hashtags: bool = False
    # The channel's name under the post, linked to the channel when public.
    signature: str = Field(default="", max_length=64)

    @field_validator("emoji")
    @classmethod
    def _no_markup(cls, value: str) -> str:
        value = value.strip()
        if any(char in value for char in "<>&"):
            raise ValueError("an emoji, not markup")
        return value


class Links(_Frozen):
    """Where the source goes: nowhere, a word in the text, a preview card or a button."""

    mode: LinkMode = "inline"
    inline_text: str = Field(default="здесь", min_length=1, max_length=40)
    button_text: str = Field(default="Читать источник", min_length=1, max_length=40)
    # Appended to the article address, e.g. "utm_source=telegram&utm_medium=channel".
    utm: str = Field(default="", max_length=200)

    @field_validator("utm")
    @classmethod
    def _query_only(cls, value: str) -> str:
        value = value.strip().lstrip("?&")
        if value and not _UTM_RE.fullmatch(value):
            raise ValueError("utm must be key=value pairs joined by &")
        return value


class Format(_Frozen):
    kind: PostFormat = "classic"
    media: MediaMode = "auto"
    caption_above_media: bool = False
    silent: bool = False
    protect_content: bool = False


class Schedule(_Frozen):
    """Slots at fixed times or every N minutes inside a daily window, on the
    chosen weekdays (0 is Monday), in the channel's time zone."""

    mode: Literal["interval", "times"] = "interval"
    every_minutes: int = Field(default=180, ge=15, le=1440)
    window_start: str = "09:00"
    window_end: str = "21:00"
    times: tuple[str, ...] = Field(default=(), max_length=MAX_SLOTS)
    days: tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6)
    # A slot moves by up to this many minutes, the same way every time it is
    # computed, so posts do not land on the round minute like a robot's.
    jitter_minutes: int = Field(default=0, ge=0, le=60)
    timezone: str = DEFAULT_TIMEZONE
    max_per_day: int = Field(default=6, ge=1, le=MAX_SLOTS)
    # Posts are written this long before their slot, so a human can read them.
    prepare_minutes: int = Field(default=20, ge=1, le=720)

    @field_validator("window_start", "window_end")
    @classmethod
    def _window_clock(cls, value: str) -> str:
        return _clock(value)

    @field_validator("times")
    @classmethod
    def _clocks(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted({_clock(item) for item in value}, key=minutes_of))

    @field_validator("days")
    @classmethod
    def _weekdays(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        days = tuple(sorted(set(value)))
        if not days or any(day < 0 or day > 6 for day in days):
            raise ValueError("days are 0 (Monday) to 6 (Sunday), at least one")
        return days

    @field_validator("timezone")
    @classmethod
    def _zone(cls, value: str) -> str:
        if value not in _zones():
            raise ValueError(f"unknown time zone {value!r}")
        return value

    @model_validator(mode="after")
    def _has_slots(self) -> Schedule:
        if self.mode == "times" and not self.times:
            raise ValueError("list at least one time")
        if self.mode == "interval" and minutes_of(self.window_end) <= minutes_of(self.window_start):
            raise ValueError("the window must end after it starts")
        return self

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


class Selection(_Frozen):
    """Which news qualify: how fresh, how relevant, and whether a story another
    channel of the same owner already told may be told again."""

    freshness_hours: int = Field(default=24, ge=1, le=168)
    min_score: float = Field(default=0.5, ge=0.0, le=1.0)
    network: NetworkPolicy = "share"
    # For "spread": a story told elsewhere is held back this long.
    network_hours: int = Field(default=12, ge=1, le=168)


class DigestPost(_Frozen):
    """A periodic round-up as a rich post: headings, a list, details blocks."""

    enabled: bool = False
    weekday: int = Field(default=4, ge=0, le=6)
    time: str = "18:00"
    items: int = Field(default=5, ge=3, le=10)
    days: int = Field(default=7, ge=1, le=31)

    @field_validator("time")
    @classmethod
    def _time(cls, value: str) -> str:
        return _clock(value)


class ChannelSettings(_Frozen):
    style: Style = Style()
    links: Links = Links()
    format: Format = Format()
    schedule: Schedule = Schedule()
    selection: Selection = Selection()
    digest: DigestPost = DigestPost()
    approval: Approval = "auto"
