# ruff: noqa: F811  (the fixtures are imported from the other tests)
"""What the API records about a reader's feed, and that it goes with the account.

Needs PostgreSQL, Valkey and ClickHouse; skipped without them.
"""

import uuid
from datetime import UTC, datetime

import numpy as np
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


async def test_the_administrator_sees_what_readers_did_and_nobody_else_does(
    api: str, events: None
) -> None:
    from radar.auth.service import set_admin
    from radar.db import session_scope
    from radar.events.writer import flush

    await seed_articles()
    async with register(api, "lena") as lena, register(api, "boss") as boss:
        await lena.post("/profiles", json=profile_spec())
        feed = (await lena.get("/feed", params={"limit": 4})).json()
        snapshot, items = feed["snapshot"], feed["items"]
        await lena.post(
            "/impressions",
            json={
                "list_id": snapshot,
                "items": [
                    {
                        "article_id": item["article_id"],
                        "position": item["position"],
                        "slot": "ranked",
                    }
                    for item in items
                ],
            },
        )
        placed = {"list_id": snapshot, "position": 1, "slot": "ranked"}
        for kind in ("open", "like"):
            await lena.post(
                "/feedback", json={"article_id": items[0]["article_id"], "kind": kind} | placed
            )
        # Opened within a second of showing up: no impression, yet it was seen.
        await lena.post(
            "/feedback",
            json={"article_id": items[2]["article_id"], "kind": "open"} | placed | {"position": 3},
        )
        refused = await lena.get("/analytics/overview")
        email = (await boss.get("/auth/me")).json()["email"]
        async with session_scope() as session:
            await set_admin(session, email, is_admin=True)
        await boss.post("/auth/logout")
        await boss.post("/auth/login", json={"email": email, "password": PASSWORD})
        await flush()
        answer = await boss.get("/analytics/overview", params={"days": 7})
        overview = answer.json()

    assert refused.status_code == 403
    assert answer.status_code == 200, answer.text
    totals = overview["totals"]
    assert (totals["seen"], totals["opened"], totals["liked"]) == (3, 2, 1)
    assert totals["ctr"] == pytest.approx(2 / 3)
    assert totals["served"] == len(items)
    [today] = [day for day in overview["daily"] if day["seen"]]
    assert today["readers"] == 1
    assert len(overview["daily"]) == 7
    assert [slot["slot"] for slot in overview["slots"]] == ["ranked"]
    assert overview["categories"][0]["category"] == "it"
    # Three articles are too few to call a source good or bad.
    assert overview["sources_best"] == []
    assert overview["queue"] == {"waiting": 0, "set_aside": 0}


async def test_a_switched_on_model_orders_the_feed_of_readers_in_its_group(
    api: str, events: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from radar.config import get_settings
    from radar.db import session_scope
    from radar.db.models import RankerModel
    from radar.events.writer import flush
    from radar.ranker import model
    from radar.ranker.features import FEATURES
    from radar.ranker.train import assemble, fit

    # A model that learned readers want the oldest news first: the opposite of
    # the hand blend, which gives fresh articles a little lift.
    rng = np.random.default_rng(5)
    examples = []
    served_at = datetime.now(UTC)
    for index in range(150):
        # In the narrow band where the test articles are: an hour apart is 0.0014.
        fresh = rng.uniform(0.04, 0.05, 20)
        for rank, position in enumerate(np.argsort(fresh)):
            label = 4 - rank * 5 // 20
            examples.append(
                (index, int(position) + 1, {"fresh": float(fresh[position])}, served_at, label)
            )
    booster = fit(assemble(examples))
    async with session_scope() as session:
        session.add(
            RankerModel(
                version="test-1",
                status="active",
                trained_from=served_at,
                trained_to=served_at,
                lists=150,
                rows=len(examples),
                metrics={},
                features=list(FEATURES),
                model=booster.model_to_string(),
            )
        )
    monkeypatch.setenv("RADAR_RANKER_SHARE", "1")
    get_settings.cache_clear()
    model.forget()

    await seed_articles()
    async with register(api, "lena") as lena:
        await lena.post("/profiles", json=profile_spec())
        feed = (await lena.get("/feed")).json()
        me = (await lena.get("/auth/me")).json()
    await flush()
    served = [
        row
        for row in await rows("user_id = %(user)s", {"user": me["id"]})
        if row["event"] == "served"
    ]

    published = [item["published_at"] for item in feed["items"] if item["slot"] == "ranked"]
    assert len(published) > 1
    assert published == sorted(published)
    assert {(row["variant"], row["model_version"]) for row in served} == {("learned", "test-1")}
