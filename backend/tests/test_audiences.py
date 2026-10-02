"""Two audiences from the jury's Q&A: specialists daily and in detail,
management weekly and in theses."""

from datetime import datetime

import httpx
import pytest

from radar.domain import AUDIENCE_PERIOD_DAYS, AUDIENCE_SCHEDULE, ScheduleDefault
from tests.test_accounts_api import api, database, profile_spec, register  # noqa: F401  (fixtures)


def test_a_specialist_reads_every_day_and_management_once_a_week() -> None:
    assert AUDIENCE_PERIOD_DAYS == {"specialist": 1, "management": 7}


def test_the_schedule_a_profile_is_offered_follows_its_audience() -> None:
    assert AUDIENCE_SCHEDULE["specialist"] == ScheduleDefault(
        cadence="weekdays", weekday=None, time="08:30"
    )
    assert AUDIENCE_SCHEDULE["management"] == ScheduleDefault(
        cadence="weekly", weekday=0, time="09:00"
    )


async def _profiles(reader: httpx.AsyncClient) -> dict[str, dict[str, object]]:
    """One profile of each audience. A registered reader, not a guest: the
    fixture removes such accounts with their digests, and queued digests of
    guests would count against the stack's limit in the next tests."""
    made = {}
    for audience in ("specialist", "management"):
        spec = {**profile_spec(f"Профиль {audience}"), "audience": audience}
        response = await reader.post("/profiles", json=spec)
        assert response.status_code == 201, response.text
        made[audience] = response.json()
    return made


def _days(digest: dict[str, str]) -> float:
    start = datetime.fromisoformat(digest["period_start"])
    end = datetime.fromisoformat(digest["period_end"])
    return round((end - start).total_seconds() / 86400, 3)


@pytest.mark.integration
async def test_a_profile_tells_its_default_period_and_schedule(api: str) -> None:  # noqa: F811
    async with register(api) as reader:
        made = await _profiles(reader)

    assert made["management"]["defaults"] == {
        "period_days": 7,
        "schedule": {"cadence": "weekly", "weekday": 0, "time": "09:00"},
    }
    assert made["specialist"]["defaults"] == {
        "period_days": 1,
        "schedule": {"cadence": "weekdays", "weekday": None, "time": "08:30"},
    }


@pytest.mark.integration
async def test_a_digest_without_a_period_takes_its_audiences_one(api: str) -> None:  # noqa: F811
    async with register(api) as reader:
        made = await _profiles(reader)
        lengths = {}
        for audience, profile in made.items():
            created = await reader.post("/digests", json={"profile_id": profile["id"]})
            assert created.status_code == 202, created.text
            lengths[audience] = _days(created.json())

    assert lengths == {"specialist": 1.0, "management": 7.0}


@pytest.mark.integration
async def test_an_explicit_period_still_wins(api: str) -> None:  # noqa: F811
    async with register(api) as reader:
        made = await _profiles(reader)
        response = await reader.post(
            "/digests", json={"profile_id": made["specialist"]["id"], "period_days": 3}
        )

    assert _days(response.json()) == 3.0
