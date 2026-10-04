"""When a scheduled digest is due, in the reader's own time zone. Pure.

A schedule is a local time of day and the days it applies to. Each run takes
the news since the previous slot: a Monday digest of a weekdays schedule
covers the weekend, a weekly one the whole week.
"""

from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

Cadence = Literal["daily", "weekdays", "weekly"]
CADENCES: tuple[Cadence, ...] = ("daily", "weekdays", "weekly")
MINUTES_IN_DAY = 24 * 60
# Every cadence has a slot within any eight consecutive days.
_SEARCH_DAYS = 8


class ScheduleError(ValueError):
    """A schedule that cannot be kept: an unknown cadence, day, time or zone."""


def zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ScheduleError(f"Неизвестный часовой пояс: {name}") from exc


def validate(cadence: str, weekday: int | None, minute: int, timezone: str) -> Cadence:
    if cadence not in CADENCES:
        raise ScheduleError("Расписание может быть ежедневным, по будням или раз в неделю.")
    if cadence == "weekly" and (weekday is None or not 0 <= weekday <= 6):
        raise ScheduleError("Для еженедельного выпуска укажите день недели.")
    if not 0 <= minute < MINUTES_IN_DAY:
        raise ScheduleError("Укажите время выпуска от 00:00 до 23:59.")
    zone(timezone)
    return cadence


def _runs_on(cadence: str, weekday: int | None, day: date) -> bool:
    if cadence == "daily":
        return True
    if cadence == "weekdays":
        return day.weekday() < 5
    return day.weekday() == weekday


def _slot(day: date, minute: int, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, time(minute // 60, minute % 60), tzinfo=tz)


def next_run(
    cadence: str, weekday: int | None, minute: int, timezone: str, after: datetime
) -> datetime:
    """The first slot strictly after `after`, in UTC."""
    tz = zone(timezone)
    start = after.astimezone(tz).date()
    for offset in range(_SEARCH_DAYS):
        day = start + timedelta(days=offset)
        if _runs_on(cadence, weekday, day) and (slot := _slot(day, minute, tz)) > after:
            return slot.astimezone(UTC)
    raise ScheduleError("По этому расписанию нет запланированных выпусков.")


def previous_run(
    cadence: str, weekday: int | None, minute: int, timezone: str, before: datetime
) -> datetime:
    """The last slot strictly before `before`, in UTC: where a run's period starts."""
    tz = zone(timezone)
    start = before.astimezone(tz).date()
    for offset in range(_SEARCH_DAYS):
        day = start - timedelta(days=offset)
        if _runs_on(cadence, weekday, day) and (slot := _slot(day, minute, tz)) < before:
            return slot.astimezone(UTC)
    raise ScheduleError("По этому расписанию нет запланированных выпусков.")
