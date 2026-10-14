"""Digests from a terminal: which ones a command line asks for, and how they are named.

The jury asked for a digest without a browser. `radar digest` takes an
audience, a saved profile or a profile file and the period, builds in its own
process and writes Markdown and DOCX; this module decides what that command
line means.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from zoneinfo import ZoneInfo

from radar.domain import AUDIENCE_PERIOD_DAYS, ProfileSpec
from radar.domain import Audience as ProfileAudience

MOSCOW = ZoneInfo("Europe/Moscow")


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


def moment(text: str) -> datetime:
    """A date and time of the command line in ISO 8601. Without an offset it is
    Moscow time, the time the digests are written in."""
    try:
        parsed = datetime.fromisoformat(text.strip())
    except ValueError as exc:
        raise ConsoleError(
            f"Дата «{text}» не в формате ISO 8601. Пример: 2026-10-03T04:27, "
            "время без смещения считается московским."
        ) from exc
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=MOSCOW)


@dataclass(frozen=True, slots=True)
class Target:
    """One digest a command line asks for: a saved profile or one from a file,
    and the period, open or fixed at either end."""

    label: str
    days: int | None = None
    profile_name: str | None = None
    spec: ProfileSpec | None = None
    start: datetime | None = None
    end: datetime | None = None

    def period(self, audience: ProfileAudience) -> int:
        return self.days or AUDIENCE_PERIOD_DAYS[audience]

    def bounds(self, audience: ProfileAudience, now: datetime) -> tuple[datetime, datetime]:
        """The end is now unless fixed, the start the period's days before
        the end unless fixed."""
        end = self.end or now
        start = self.start or end - timedelta(days=self.period(audience))
        return start, end


def period_text(start: datetime, end: datetime) -> str:
    """02.10.2026 04:27 - 03.10.2026 04:27 МСК, in the time the digests use."""
    shown = "%d.%m.%Y %H:%M"
    return f"{start.astimezone(MOSCOW):{shown}} - {end.astimezone(MOSCOW):{shown}} МСК"


def _check_period(
    days: int | None, start: datetime | None, end: datetime | None, now: datetime
) -> None:
    """A fixed start leaves --days nothing to count and has to come before the end."""
    if start is None:
        return
    if days is not None:
        raise ConsoleError("Укажите что-то одно: --days или --period-start.")
    last = end or now
    if start >= last:
        raise ConsoleError(f"Начало периода должно быть раньше конца: {period_text(start, last)}.")


def targets(
    audience: Audience | None,
    profile: str | None,
    profile_file: Path | None,
    days: int | None,
    start: datetime | None = None,
    end: datetime | None = None,
    now: datetime | None = None,
) -> list[Target]:
    """The digests to build. Nothing chosen means both audiences' examples."""
    chosen = [option for option in (audience, profile, profile_file) if option is not None]
    if len(chosen) > 1:
        raise ConsoleError("Укажите что-то одно: --audience, --profile или --profile-file.")
    _check_period(days, start, end, now or datetime.now(UTC))
    if profile is not None:
        return [Target(label="profile", days=days, profile_name=profile, start=start, end=end)]
    if profile_file is not None:
        try:
            spec = ProfileSpec.model_validate_json(profile_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ConsoleError(f"Профиль из {profile_file} не прочитан: {exc}") from exc
        return [Target(label=profile_file.stem, days=days, spec=spec, start=start, end=end)]
    wanted: list[ProfileAudience] = (
        ["specialist", "management"]
        if audience in (None, Audience.both)
        else ["management" if audience is Audience.management else "specialist"]
    )
    return [
        Target(label=name, days=days, profile_name=AUDIENCE_PROFILES[name], start=start, end=end)
        for name in wanted
    ]


def file_stem(label: str, start: datetime, end: datetime, built: datetime) -> str:
    """specialist-1d-20261003-0930: who it is for, the period in whole days,
    when it was built."""
    days = max(1, round((end - start) / timedelta(days=1)))
    return f"{label}-{days}d-{built:%Y%m%d-%H%M}"


def addresses(text: str) -> list[str]:
    """The addresses of a --sources file: one per line, blank lines and lines
    starting with "#" skipped, each address once."""
    lines = (line.strip() for line in text.splitlines())
    return list(dict.fromkeys(line for line in lines if line and not line.startswith("#")))


def progress_line(stage: str | None, progress: float) -> str:
    label = STAGE_LABELS.get(stage or "", stage or "В очереди")
    return f"{progress:4.0%}  {label}"
