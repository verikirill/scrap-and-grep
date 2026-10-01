# ruff: noqa: F811  (the fixtures are imported from the other tests)
"""What the API records about a reader's feed, and that it goes with the account.

Needs PostgreSQL, Valkey and ClickHouse; skipped without them.
"""

import uuid

import pytest

from tests.test_accounts_api import (  # noqa: F401  (fixtures)
    PASSWORD,
    api,
    database,
    profile_spec,
    register,
    seed_articles,
)
from tests.test_events import (  # noqa: F401  (fixtures)
    clickhouse_up,
    events,
    events_on,
    rows,
)


async def test_the_feed_records_what_was_shown_seen_and_marked(api: str, events: None) -> None:
    from radar.events.writer import flush

    ids = await seed_articles()
    async with register(api, "lena") as lena:
        await lena.post("/profiles", json=profile_spec())
        feed = (await lena.get("/feed", params={"limit": 3})).json()
        first, second = feed["items"][0], feed["items"][1]
        seen = await lena.post(
            "/impressions",
            json={
                "context": "feed",
                "list_id": feed["snapshot"],
                "items": [
                    {"article_id": second["article_id"], "position": 2, "slot": second["slot"]},
                    # An id that is no article is not recorded.
                    {"article_id": 10**9, "position": 3, "slot": "ranked"},
                ],
            },
        )
        placement = {"list_id": feed["snapshot"], "position": 1, "slot": first["slot"]}
        for active in (True, False):
            await lena.post(
                "/feedback",
                json={"article_id": first["article_id"], "kind": "like", "active": active}
                | placement,
            )
        me = (await lena.get("/auth/me")).json()
    await flush()
    recorded = await rows("user_id = %(user)s", {"user": me["id"]})

    assert seen.status_code == 204
    served = [row for row in recorded if row["event"] == "served"]
    assert [row["position"] for row in served] == [1, 2, 3]
    assert {row["request_id"] for row in served} == {uuid.UUID(feed["snapshot"])}
    assert [row["article_id"] for row in served] == [item["article_id"] for item in feed["items"]]
    # Training reads the parts of the score as serving saw them.
    assert served[0]["features"]["score"] == pytest.approx(first["score"], abs=1e-3)
    assert {"interest", "fresh", "confidence"} <= served[0]["features"].keys()
    assert {row["variant"] for row in served} == {"hand"}
    [impression] = [row for row in recorded if row["event"] == "impression"]
    assert impression["article_id"] == second["article_id"]
    assert (impression["position"], impression["category"]) == (2, "it")
    assert impression["source_id"] == second["source_id"]
    marks = [(row["event"], row["position"]) for row in recorded if "like" in row["event"]]
    assert marks == [("like", 1), ("like_undo", 1)]
    assert set(ids.values()) >= {row["article_id"] for row in recorded}


async def test_a_deleted_account_takes_its_events_along(api: str, events: None) -> None:
    from radar.events.writer import flush

    await seed_articles()
    async with register(api, "max") as max_:
        await max_.post("/profiles", json=profile_spec())
        await max_.get("/feed")
        me = (await max_.get("/auth/me")).json()
        await flush()
        before = await rows("user_id = %(user)s", {"user": me["id"]})
        deleted = await max_.post("/auth/me/delete", json={"password": PASSWORD})

    await flush()
    assert before
    assert deleted.status_code == 204
    assert await rows("user_id = %(user)s", {"user": me["id"]}) == []
