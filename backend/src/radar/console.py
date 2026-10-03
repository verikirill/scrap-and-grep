"""Digests from a terminal: which ones a command line asks for, and how they are named.

The jury asked for a digest without a browser. `radar digest` takes an
audience, a saved profile or a profile file, builds in its own process and
writes Markdown and DOCX; this module decides what that command line means.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from radar.domain import AUDIENCE_PERIOD_DAYS, ProfileSpec
from radar.domain import Audience as ProfileAudience


class Audience(StrEnum):
    specialist = "specialist"
    management = "management"
    both = "both"


# The demo account's example profile for each audience.
AUDIENCE_PROFILES: dict[ProfileAudience, str] = {
    "specialist": "Специалист по ИБ АСУ ТП",
    "management": "Руководство и сотрудники: кибербезопасность",
}

STAGE_LABELS = {
    "prepare": "Готовим публикации",
    "retrieve": "Ищем по интересам",
    "grade": "Оцениваем релевантность",
    "select": "Отбираем и убираем повторы",
    "summarize": "Пишем записи",
    "compose": "Собираем выпуск",
    "persist": "Сохраняем",
}


class ConsoleError(ValueError):
    """A command line that asks for nothing sensible, in words for the reader."""


@dataclass(frozen=True, slots=True)
class Target:
    """One digest a command line asks for: a saved profile or one from a file."""

    label: str
    days: int | None = None
    profile_name: str | None = None
    spec: ProfileSpec | None = None

    def period(self, audience: ProfileAudience) -> int:
        return self.days or AUDIENCE_PERIOD_DAYS[audience]


def targets(
    audience: Audience | None,
    profile: str | None,
    profile_file: Path | None,
    days: int | None,
) -> list[Target]:
    """The digests to build. Nothing chosen means both audiences' examples."""
    chosen = [option for option in (audience, profile, profile_file) if option is not None]
    if len(chosen) > 1:
        raise ConsoleError("Укажите что-то одно: --audience, --profile или --profile-file.")
    if profile is not None:
        return [Target(label="profile", days=days, profile_name=profile)]
    if profile_file is not None:
        try:
            spec = ProfileSpec.model_validate_json(profile_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ConsoleError(f"Профиль из {profile_file} не прочитан: {exc}") from exc
        return [Target(label=profile_file.stem, days=days, spec=spec)]
    wanted: list[ProfileAudience] = (
        ["specialist", "management"]
        if audience in (None, Audience.both)
        else ["management" if audience is Audience.management else "specialist"]
    )
    return [Target(label=name, days=days, profile_name=AUDIENCE_PROFILES[name]) for name in wanted]


def file_stem(label: str, days: int, now: datetime) -> str:
    """specialist-1d-20261003-0930: who it is for, the period, when it was built."""
    return f"{label}-{days}d-{now:%Y%m%d-%H%M}"


def progress_line(stage: str | None, progress: float) -> str:
    label = STAGE_LABELS.get(stage or "", stage or "В очереди")
    return f"{progress:4.0%}  {label}"
