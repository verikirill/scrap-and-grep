# ruff: noqa: F811  (the fixtures are imported from the accounts tests)
"""Ready pictures, the shared accounts behind one-click sign-in, and the guest
button being off unless asked for."""

import uuid
from collections.abc import Iterator
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import select, update

from radar.auth.shared import SHARED_ACCOUNTS, is_service_address
from radar.avatars import AVATAR_PRESETS, preset_for
from radar.config import Settings
from radar.seed import DEFAULT_PROFILES
from tests.test_accounts_api import (  # noqa: F401  (fixtures)
    PASSWORD,
    api,
    client,
    database,
    register,
)


def _png() -> bytes:
    out = BytesIO()
    Image.new("RGB", (300, 300), "teal").save(out, "PNG")
    return out.getvalue()


@pytest.fixture
def settings_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    """Environment changes that the cached settings pick up, undone after the test."""
    from radar.config import get_settings

    get_settings.cache_clear()
    yield monkeypatch
    monkeypatch.undo()
    get_settings.cache_clear()


def test_guest_sign_in_is_off_unless_asked_for(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RADAR_DEMO_LOGIN", raising=False)
    monkeypatch.delenv("RADAR_PRESET_LOGIN", raising=False)

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.demo_login is False
    assert settings.preset_login is True


def test_a_stored_picture_wins_and_a_missing_one_is_stable_per_account() -> None:
    user_id = uuid.uuid7()

    assert preset_for(user_id, "teal") == "teal"
    # Nothing stored, or something that is no longer one of the nine: the
    # same picture each time for the same account.
    assert preset_for(user_id, None) == preset_for(user_id, "violet") in AVATAR_PRESETS
    spread = {preset_for(uuid.uuid7(), None) for _ in range(200)}
    assert len(spread) > 1


def test_made_up_addresses_are_told_apart_from_real_ones() -> None:
    assert is_service_address("reader@radar.local")
    assert is_service_address("guest-1@guest.radar.local")
    assert not is_service_address("reader@radar.local.example.org")
    assert not is_service_address("anna@example.org")


async def test_a_new_reader_gets_one_of_the_ready_pictures_at_random(
    api: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from radar.auth import service
    from radar.db import session_scope
    from radar.db.models import User

    picks = iter(["yellow", "purple"])
    monkeypatch.setattr(service, "random_preset", lambda: next(picks))
    async with register(api, "anna") as anna, register(api, "boris") as boris:
        first = (await anna.get("/auth/me")).json()
        second = (await boris.get("/auth/me")).json()
    async with session_scope() as session:
        stored = await session.scalar(
            select(User.avatar_preset).where(User.id == uuid.UUID(first["id"]))
        )

    assert (first["avatar_preset"], second["avatar_preset"]) == ("yellow", "purple")
    assert stored == "yellow"
    assert first["avatar_url"] is None


async def test_an_account_from_before_the_pictures_shows_the_same_one_each_time(
    api: str,
) -> None:
    from radar.db import session_scope
    from radar.db.models import User

    async with register(api, "old") as reader:
        user_id = uuid.UUID((await reader.get("/auth/me")).json()["id"])
        async with session_scope() as session:
            await session.execute(update(User).where(User.id == user_id).values(avatar_preset=None))
        first = (await reader.get("/auth/me")).json()["avatar_preset"]
        again = (await reader.get("/auth/me")).json()["avatar_preset"]

    assert first == again == preset_for(user_id, None)


async def test_a_ready_picture_and_a_photo_replace_each_other(api: str) -> None:
    async with register(api, "vera") as vera:
        await vera.put("/auth/me/avatar", content=_png(), headers={"Content-Type": "image/png"})
        picked = await vera.put("/auth/me/avatar-preset", json={"preset": "orange"})
        after_pick = (await vera.get("/auth/me")).json()
        photo_after_pick = await vera.get("/auth/me/avatar")
        uploaded = await vera.put(
            "/auth/me/avatar", content=_png(), headers={"Content-Type": "image/png"}
        )
        after_upload = (await vera.get("/auth/me")).json()
        unknown = await vera.put("/auth/me/avatar-preset", json={"preset": "violet"})

    assert picked.status_code == 200
    assert picked.json() == {"avatar_url": None, "avatar_preset": "orange"}
    assert after_pick["avatar_url"] is None
    assert after_pick["avatar_preset"] == "orange"
    assert photo_after_pick.status_code == 404
    # The photo is shown again; the pick stays for when the photo goes.
    assert after_upload["avatar_url"] == uploaded.json()["avatar_url"] is not None
    assert after_upload["avatar_preset"] == "orange"
    assert unknown.status_code == 422


async def test_everyone_enters_the_same_shared_account_with_one_click(api: str) -> None:
    async with client(api) as first, client(api) as second:
        entered = await first.post("/auth/preset/reader")
        await second.post("/auth/preset/reader")
        mine = (await first.get("/auth/me")).json()
        theirs = (await second.get("/auth/me")).json()
        profiles = (await first.get("/profiles")).json()

    assert entered.status_code == 200
    assert entered.json()["is_shared"] is True
    assert mine["id"] == theirs["id"]
    assert mine["display_name"] == "Читатель"
    assert mine["is_shared"] is True
    assert mine["is_demo"] is False
    # Many people use it: none of them is walked through the introduction.
    assert mine["onboarded_at"] is not None
    assert mine["avatar_preset"] == SHARED_ACCOUNTS["reader"].avatar
    assert sorted(p["spec"]["name"] for p in profiles) == sorted(p.name for p in DEFAULT_PROFILES)


async def test_one_click_makes_the_shared_account_where_the_seeding_did_not(api: str) -> None:
    from sqlalchemy import delete

    from radar.db import session_scope
    from radar.db.models import User

    async with session_scope() as session:
        await session.execute(delete(User).where(User.email == SHARED_ACCOUNTS["analyst"].email))
    async with client(api) as visitor:
        entered = await visitor.post("/auth/preset/analyst")
        profiles = (await visitor.get("/profiles")).json()

    assert entered.status_code == 200
    assert len(profiles) == len(SHARED_ACCOUNTS["analyst"].profiles)


async def test_the_analyst_starts_with_the_security_profiles(api: str) -> None:
    async with client(api) as visitor:
        await visitor.post("/auth/preset/analyst")
        me = (await visitor.get("/auth/me")).json()
        profiles = (await visitor.get("/profiles")).json()
        unknown = await visitor.post("/auth/preset/admin")

    assert me["display_name"] == "Аналитик ИБ"
    assert sorted(p["spec"]["name"] for p in profiles) == sorted(
        SHARED_ACCOUNTS["analyst"].profiles
    )
    assert unknown.status_code == 404


@pytest.mark.parametrize(("value", "expected"), [("true", 200), ("false", 404)])
async def test_one_click_sign_in_follows_the_setting(
    api: str, settings_env: pytest.MonkeyPatch, value: str, expected: int
) -> None:
    settings_env.setenv("RADAR_PRESET_LOGIN", value)
    async with client(api) as visitor:
        meta = (await visitor.get("/meta")).json()
        entered = await visitor.post("/auth/preset/reader")
        me = (await visitor.get("/auth/me")).json()

    assert meta["preset_login"] is (value == "true")
    assert entered.status_code == expected
    assert (me is not None) is (expected == 200)


async def test_guest_button_is_off_on_a_stack_with_the_defaults(
    api: str, settings_env: pytest.MonkeyPatch
) -> None:
    settings_env.delenv("RADAR_DEMO_LOGIN", raising=False)
    settings_env.setenv("RADAR_AUTH", "on")
    async with client(api) as visitor:
        meta = (await visitor.get("/meta")).json()
        guest = await visitor.post("/auth/demo")

    assert meta["demo_login"] is False
    assert guest.status_code == 404


async def test_a_shared_account_cannot_be_deleted_or_entered_with_a_password(api: str) -> None:
    from radar.db import session_scope
    from radar.db.models import User

    email = SHARED_ACCOUNTS["reader"].email
    async with client(api) as visitor:
        await visitor.post("/auth/preset/reader")
        refused = await visitor.post("/auth/me/delete", json={"password": ""})
        still_in = (await visitor.get("/auth/me")).json()
        by_password = await visitor.post("/auth/login", json={"email": email, "password": ""})
        taken = await visitor.post(
            "/auth/register",
            json={"email": email, "password": PASSWORD, "display_name": "Чужой"},
        )
    async with session_scope() as session:
        exists = await session.scalar(select(User.id).where(User.email == email))

    assert refused.status_code == 403
    assert still_in is not None
    assert exists is not None
    assert by_password.status_code == 401
    assert taken.status_code == 422


async def test_seeding_the_shared_accounts_again_keeps_edits_and_restores_removals(
    api: str,
) -> None:
    from radar.db import session_scope
    from radar.db.models import Profile, User
    from radar.seed import seed_defaults

    async with client(api) as visitor:
        await visitor.post("/auth/preset/reader")
        first, second, *_ = (await visitor.get("/profiles")).json()
        edited = {**first["spec"], "max_items": 3}
        await visitor.put(f"/profiles/{first['id']}", json=edited)
        await visitor.delete(f"/profiles/{second['id']}")
    async with session_scope() as session:
        again = await seed_defaults(session)
    async with session_scope() as session:
        reader_id = await session.scalar(
            select(User.id).where(User.email == SHARED_ACCOUNTS["reader"].email)
        )
        specs = {
            profile.name: profile.spec
            for profile in await session.scalars(
                select(Profile).where(Profile.user_id == reader_id)
            )
        }

    assert again["shared_accounts"] == 0
    assert set(specs) == {p.name for p in DEFAULT_PROFILES}
    assert specs[first["spec"]["name"]]["max_items"] == 3
