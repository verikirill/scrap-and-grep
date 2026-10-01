"""When a scheduled digest is due, in the reader's own time."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from radar.digest_schedule import ScheduleError, next_run, previous_run, validate

MOSCOW = "Europe/Moscow"


def _msk(*parts: int) -> datetime:
    return datetime(*parts, tzinfo=ZoneInfo(MOSCOW))  # type: ignore[misc]


def test_a_daily_digest_comes_at_the_readers_hour_today_or_tomorrow() -> None:
    nine = 9 * 60

    assert next_run("daily", None, nine, MOSCOW, _msk(2026, 10, 2, 8, 0)) == _msk(2026, 10, 2, 9)
    assert next_run("daily", None, nine, MOSCOW, _msk(2026, 10, 2, 9, 0)) == _msk(2026, 10, 3, 9)
    # Returned in UTC, the way it is stored.
    assert next_run("daily", None, nine, MOSCOW, _msk(2026, 10, 2, 8, 0)).tzinfo == UTC


def test_weekdays_skip_the_weekend_and_mondays_cover_it() -> None:
    nine = 9 * 60
    friday_evening = _msk(2026, 10, 2, 18, 0)  # a Friday

    monday = next_run("weekdays", None, nine, MOSCOW, friday_evening)

    assert monday == _msk(2026, 10, 5, 9)
    # The Monday digest takes the news since the Friday one: nothing is lost.
    assert previous_run("weekdays", None, nine, MOSCOW, monday) == _msk(2026, 10, 2, 9)


def test_a_weekly_digest_comes_on_its_day() -> None:
    sunday = 6
    run = next_run("weekly", sunday, 20 * 60, MOSCOW, _msk(2026, 10, 2, 12, 0))

    assert run == _msk(2026, 10, 4, 20)
    assert previous_run("weekly", sunday, 20 * 60, MOSCOW, run) == _msk(2026, 9, 27, 20)


def test_the_local_hour_holds_when_the_clocks_change() -> None:
    # Berlin leaves summer time on 25 October 2026: 09:00 is 07:00 UTC before, 08:00 after.
    before = next_run("daily", None, 9 * 60, "Europe/Berlin", datetime(2026, 10, 24, 6, tzinfo=UTC))
    after = next_run("daily", None, 9 * 60, "Europe/Berlin", before)

    assert (before.hour, after.hour) == (7, 8)


@pytest.mark.parametrize(
    ("cadence", "weekday", "minute", "zone"),
    [
        ("hourly", None, 540, MOSCOW),
        ("weekly", None, 540, MOSCOW),
        ("weekly", 7, 540, MOSCOW),
        ("daily", None, 1440, MOSCOW),
        ("daily", None, 540, "Mars/Olympus"),
        ("daily", None, 540, "../../etc/passwd"),
    ],
)
def test_a_schedule_that_cannot_be_kept_is_refused(
    cadence: str, weekday: int | None, minute: int, zone: str
) -> None:
    with pytest.raises(ScheduleError):
        validate(cadence, weekday, minute, zone)
