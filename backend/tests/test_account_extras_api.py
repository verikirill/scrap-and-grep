# ruff: noqa: F811  (the fixtures are imported from the accounts tests)
"""A reader's picture, and digests their schedule builds."""

import uuid
from datetime import UTC, datetime, timedelta
from io import BytesIO

from PIL import Image

from tests.test_accounts_api import (  # noqa: F401  (fixtures)
    api,
    client,
    database,
    profile_spec,
    register,
)


def _png(size: tuple[int, int] = (640, 480)) -> bytes:
    out = BytesIO()
    Image.new("RGB", size, "teal").save(out, "PNG")
    return out.getvalue()


async def test_a_reader_sets_a_picture_only_they_get_back(api: str) -> None:
    async with register(api, "lena") as lena, register(api, "max") as max_:
        upload = await lena.put(
            "/auth/me/avatar", content=_png(), headers={"Content-Type": "image/png"}
        )
        me = (await lena.get("/auth/me")).json()
        picture = await lena.get("/auth/me/avatar")
        theirs = await max_.get("/auth/me/avatar")
        not_a_picture = await lena.put("/auth/me/avatar", content=b"%PDF-1.7 not an image")
        too_big = await lena.put("/auth/me/avatar", content=b"\0" * 5_000_001)
        removed = await lena.delete("/auth/me/avatar")
        after = (await lena.get("/auth/me")).json()

    assert upload.status_code == 200
    assert me["avatar_url"] == upload.json()["avatar_url"]
    assert me["avatar_url"].startswith("/api/v1/auth/me/avatar?v=")
    assert picture.headers["content-type"] == "image/webp"
    assert Image.open(BytesIO(picture.content)).size == (256, 256)
    # Every reader gets their own picture only: the other one has none.
    assert theirs.status_code == 404
    assert not_a_picture.status_code == 415
    assert too_big.status_code == 413
    assert removed.status_code == 204
    assert after["avatar_url"] is None


async def test_a_schedule_starts_one_digest_per_slot_with_the_news_since_the_last(
    api: str,
) -> None:
    from radar.db import session_scope
    from radar.db.models import DigestSchedule
    from radar.worker import tasks

    async with register(api, "lena") as lena, register(api, "max") as stranger:
        profile = (await lena.post("/profiles", json=profile_spec())).json()
        path = f"/profiles/{profile['id']}/schedule"
        bad_zone = await lena.put(
            path, json={"cadence": "daily", "time": "09:00", "timezone": "Mars/Olympus"}
        )
        weekly_without_day = await lena.put(
            path, json={"cadence": "weekly", "time": "09:00", "timezone": "Europe/Moscow"}
        )
        not_theirs = await stranger.put(
            path, json={"cadence": "daily", "time": "09:00", "timezone": "Europe/Moscow"}
        )
        saved = await lena.put(
            path, json={"cadence": "weekdays", "time": "08:30", "timezone": "Europe/Moscow"}
        )

        # The slot comes: as if 08:30 had passed a minute ago.
        async with session_scope() as session:
            schedule = await session.get(DigestSchedule, uuid.UUID(profile["id"]))
            assert schedule is not None
            schedule.next_run_at = datetime.now(UTC) - timedelta(minutes=1)
        started = await tasks.run_digest_schedules()
        again = await tasks.run_digest_schedules()
        digests = (await lena.get("/digests")).json()
        listed = (await lena.get("/digest-schedules")).json()
        removed = await lena.delete(path)
        after = (await lena.get("/digest-schedules")).json()

    assert bad_zone.status_code == 422
    assert weekly_without_day.status_code == 422
    assert not_theirs.status_code == 404
    assert saved.status_code == 200
    assert saved.json()["time"] == "08:30"
    assert datetime.fromisoformat(saved.json()["next_run_at"]) > datetime.now(UTC)
    # One digest for the slot, however often the scheduler looks.
    assert (started, again) == (1, 0)
    [digest] = digests
    assert digest["origin"] == "schedule"
    assert digest["profile_id"] == profile["id"]
    tasks.build_digest.kiq.assert_awaited_once_with(digest["id"])  # type: ignore[attr-defined]
    # The next slot is ahead again, and the last run is remembered.
    [schedule_out] = listed
    assert datetime.fromisoformat(schedule_out["next_run_at"]) > datetime.now(UTC)
    assert schedule_out["last_digest_id"] == digest["id"]
    assert removed.status_code == 204
    assert after == []


async def test_one_broken_schedule_does_not_stop_the_others(api: str) -> None:
    from radar.db import session_scope
    from radar.db.models import DigestSchedule, Profile
    from radar.store import schedules as schedule_store

    async with register(api, "lena") as lena:
        good = (await lena.post("/profiles", json=profile_spec("Сети"))).json()
        bad = (await lena.post("/profiles", json=profile_spec("Старый"))).json()
        for profile in (good, bad):
            await lena.put(
                f"/profiles/{profile['id']}/schedule",
                json={"cadence": "daily", "time": "09:00", "timezone": "Europe/Moscow"},
            )
        now = datetime.now(UTC)
        async with session_scope() as session:
            # A profile stored before a rule got stricter: it no longer validates.
            broken = await session.get(Profile, uuid.UUID(bad["id"]))
            assert broken is not None
            broken.spec = {"name": "Старый"}
            for profile in (good, bad):
                schedule = await session.get(DigestSchedule, uuid.UUID(profile["id"]))
                assert schedule is not None
                schedule.next_run_at = now - timedelta(minutes=1)
        async with session_scope() as session:
            started = await schedule_store.start_due(session, now, max_active_total=10)
        async with session_scope() as session:
            waiting = await session.get(DigestSchedule, uuid.UUID(bad["id"]))
            assert waiting is not None
            retry_at = waiting.next_run_at

    assert len(started) == 1
    # The broken one waits and tries again, instead of blocking every minute.
    assert retry_at == now + schedule_store.RETRY_AFTER
