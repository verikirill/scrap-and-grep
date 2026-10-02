"""Two audiences from the jury's Q&A: specialists daily and in detail,
management weekly and in theses."""

from datetime import datetime

import pytest

from radar.domain import AUDIENCE_PERIOD_DAYS, AUDIENCE_SCHEDULE, ScheduleDefault
from tests.test_accounts_api import api, client, database, profile_spec  # noqa: F401  (fixtures)


def test_a_specialist_reads_every_day_and_management_once_a_week() -> None:
    assert AUDIENCE_PERIOD_DAYS == {"specialist": 1, "management": 7}


def test_the_schedule_a_profile_is_offered_follows_its_audience() -> None:
    assert AUDIENCE_SCHEDULE["specialist"] == ScheduleDefault(
        cadence="weekdays", weekday=None, time="08:30"
    )
    assert AUDIENCE_SCHEDULE["management"] == ScheduleDefault(
        cadence="weekly", weekday=0, time="09:00"
    )


@pytest.mark.integration
async def test_a_profile_tells_its_default_period_and_schedule(api: str) -> None:  # noqa: F811
    async with client(api) as guest:
        await guest.post("/auth/demo")
        profiles = (await guest.get("/profiles")).json()

    by_audience = {profile["spec"]["audience"]: profile["defaults"] for profile in profiles}
    assert by_audience["management"] == {
        "period_days": 7,
        "schedule": {"cadence": "weekly", "weekday": 0, "time": "09:00"},
    }
    assert by_audience["specialist"] == {
        "period_days": 1,
        "schedule": {"cadence": "weekdays", "weekday": None, "time": "08:30"},
    }


@pytest.mark.integration
async def test_a_digest_without_a_period_takes_its_audiences_one(api: str) -> None:  # noqa: F811
    async with client(api) as guest:
        await guest.post("/auth/demo")
        profiles = (await guest.get("/profiles")).json()
        lengths = {}
        for audience in ("specialist", "management"):
            profile = next(item for item in profiles if item["spec"]["audience"] == audience)
            created = await guest.post("/digests", json={"profile_id": profile["id"]})
            assert created.status_code == 202, created.text
            body = created.json()
            start = datetime.fromisoformat(body["period_start"])
            end = datetime.fromisoformat(body["period_end"])
            lengths[audience] = round((end - start).total_seconds() / 86400, 3)

    assert lengths == {"specialist": 1.0, "management": 7.0}


@pytest.mark.integration
async def test_an_explicit_period_still_wins(api: str) -> None:  # noqa: F811
    async with client(api) as guest:
        await guest.post("/auth/demo")
        created = await guest.post("/profiles", json=profile_spec())
        response = await guest.post(
            "/digests", json={"profile_id": created.json()["id"], "period_days": 3}
        )
        body = response.json()

    start = datetime.fromisoformat(body["period_start"])
    end = datetime.fromisoformat(body["period_end"])
    assert round((end - start).total_seconds() / 86400, 3) == 3.0
