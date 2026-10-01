# ruff: noqa: F811  (the fixtures are imported from the accounts tests)
"""A profile that follows its reader: marks in, weights and suggestions out."""

import uuid
from typing import Any

import httpx
import pytest

from radar.recsys.adaptation import adapt_reader
from tests.test_accounts_api import (  # noqa: F401  (fixtures)
    api,
    client,
    database,
    profile_spec,
    register,
    seed_articles,
)


async def _like(reader: httpx.AsyncClient, *article_ids: int) -> None:
    for article_id in article_ids:
        response = await reader.post("/feedback", json={"article_id": article_id, "kind": "like"})
        assert response.status_code == 204


async def _reader_id(reader: httpx.AsyncClient) -> uuid.UUID:
    return uuid.UUID((await reader.get("/auth/me")).json()["id"])


async def test_marks_reweigh_an_interest_and_suggest_what_it_does_not_cover(api: str) -> None:
    ids = await seed_articles()
    async with register(api, "lena") as lena, register(api, "max") as stranger:
        profile = (await lena.post("/profiles", json=profile_spec())).json()
        # The network articles are what the profile's interest finds; the
        # cooking ones it does not, and three of them make a subject.
        await _like(lena, ids["vpn"], ids["router"], ids["router2"])
        await _like(lena, ids["soup"], ids["soup2"], ids["cake"])
        seen = await lena.post(
            "/impressions", json={"article_ids": list(ids.values()), "context": "feed"}
        )
        await adapt_reader(await _reader_id(lena))
        learned = (await lena.get(f"/profiles/{profile['id']}/adaptation")).json()
        not_theirs = await stranger.get(f"/profiles/{profile['id']}/adaptation")

        [suggestion] = learned["suggestions"]
        accepted = await lena.post(
            f"/profiles/{profile['id']}/suggestions/{suggestion['id']}/accept"
        )
        await adapt_reader(await _reader_id(lena))
        after = (await lena.get(f"/profiles/{profile['id']}/adaptation")).json()

    assert seen.status_code == 204
    [net] = learned["interests"]
    assert net["factor"] > 1.0
    assert net["weight"] > net["stated_weight"]
    assert net["positives"] >= 3.0
    # Three likes are enough to turn the interest towards what was liked.
    assert net["drift"] > 0.0
    assert suggestion["kind"] == "interest"
    assert suggestion["source"] == "likes"
    assert {article["id"] for article in suggestion["articles"]} <= {
        ids["soup"],
        ids["soup2"],
        ids["cake"],
    }
    assert not_theirs.status_code == 404
    # Accepting is an edit: a new version with the suggested interest in it.
    assert accepted.status_code == 200
    changed = accepted.json()
    assert changed["version"] == profile["version"] + 1
    assert [interest["title"] for interest in changed["spec"]["interests"]][-1] == suggestion[
        "title"
    ]
    # The new interest covers the cooking articles now: nothing to suggest again.
    assert after["suggestions"] == []


async def test_a_reset_forgets_old_marks_and_off_means_the_stated_profile(api: str) -> None:
    ids = await seed_articles()
    async with register(api, "lena") as lena:
        profile = (await lena.post("/profiles", json=profile_spec())).json()
        path = f"/profiles/{profile['id']}/adaptation"
        await _like(lena, ids["vpn"], ids["router"], ids["router2"])
        await adapt_reader(await _reader_id(lena))
        before = (await lena.get(path)).json()

        reset = (await lena.post(f"{path}/reset")).json()
        await adapt_reader(await _reader_id(lena))
        after_reset = (await lena.get(path)).json()

        await _like(lena, ids["soup"])
        off = (await lena.patch(path, json={"adaptive": False})).json()
        listed = (await lena.get("/profiles")).json()

    assert before["interests"][0]["factor"] > 1.0
    assert reset["since"] is not None
    # Marks from before the reset no longer teach the profile.
    assert after_reset["interests"][0]["factor"] == 1.0
    assert off["adaptive"] is False
    assert off["interests"][0]["weight"] == off["interests"][0]["stated_weight"]
    assert [item["adaptive"] for item in listed if item["id"] == profile["id"]] == [False]


async def test_impressions_take_known_articles_from_a_signed_in_reader_only(api: str) -> None:
    ids = await seed_articles()
    async with register(api, "lena") as lena, client(api) as nobody:
        unknown = await lena.post("/impressions", json={"article_ids": [987654321]})
        too_many = await lena.post("/impressions", json={"article_ids": list(range(1, 62))})
        anonymous = await nobody.post("/impressions", json={"article_ids": [ids["vpn"]]})

    assert unknown.status_code == 204
    assert too_many.status_code == 422
    assert anonymous.status_code == 401


async def test_a_reset_during_a_recomputation_is_not_overwritten(
    api: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import UTC, datetime

    from radar.db import session_scope
    from radar.db.models import Profile
    from radar.recsys import adaptation

    ids = await seed_articles()
    learn = adaptation._learn

    async def learn_then_reset(*args: Any, **kwargs: Any) -> Any:
        # The reader presses "start over" while the worker is still computing.
        result = await learn(*args, **kwargs)
        async with session_scope() as session:
            profile = await session.get(Profile, args[1].id)
            assert profile is not None
            profile.adapt_since = datetime.now(UTC)
        return result

    monkeypatch.setattr(adaptation, "_learn", learn_then_reset)
    async with register(api, "lena") as lena:
        profile = (await lena.post("/profiles", json=profile_spec())).json()
        await _like(lena, ids["vpn"], ids["router"], ids["router2"])
        updated = await adapt_reader(await _reader_id(lena))
        after = (await lena.get(f"/profiles/{profile['id']}/adaptation")).json()

    assert updated == 0
    assert after["interests"][0]["factor"] == 1.0
    assert after["updated_at"] is None
