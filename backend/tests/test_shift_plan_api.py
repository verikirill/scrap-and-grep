# ruff: noqa: F811  (the fixtures are imported from the other tests)
"""The ticks of a shift plan: kept with the issue for its reader.

Needs PostgreSQL; skipped without it.
"""

import uuid

import pytest

from tests.test_accounts_api import (  # noqa: F401
    api,
    database,
    finished_digest,
    register,
    seed_articles,
)

pytestmark = pytest.mark.integration


async def _make_urgent(digest_id: str, article_id: int) -> None:
    """One entry of the issue becomes an urgent vulnerability with an update to
    install, the kind of entry the shift plan lists."""
    from sqlalchemy import update

    from radar.db import session_scope
    from radar.db.models import DigestItem

    async with session_scope() as session:
        await session.execute(
            update(DigestItem)
            .where(
                DigestItem.digest_id == uuid.UUID(digest_id), DigestItem.article_id == article_id
            )
            .values(
                kind="vulnerability",
                priority="high",
                card={"vulnerability": {"fix": "Обновить прошивку до 7.4.9"}},
            )
        )


async def test_a_ticked_line_of_the_shift_plan_stays_with_the_issue(api: str) -> None:
    ids = await seed_articles()
    async with register(api, "olga") as owner, register(api, "petr") as other:
        digest_id = await finished_digest(owner, ids)
        await _make_urgent(digest_id, ids["vpn"])
        plan = (await owner.get(f"/digests/{digest_id}")).json()["plan"]
        url = plan[0]["url"]

        ticked = await owner.put(f"/digests/{digest_id}/plan", json={"url": url, "done": True})
        again = await owner.put(f"/digests/{digest_id}/plan", json={"url": url, "done": True})
        reloaded = (await owner.get(f"/digests/{digest_id}")).json()["plan"]
        stranger = await other.put(f"/digests/{digest_id}/plan", json={"url": url, "done": False})
        elsewhere = await owner.put(
            f"/digests/{digest_id}/plan", json={"url": "https://example.org/soup", "done": True}
        )
        unticked = await owner.put(f"/digests/{digest_id}/plan", json={"url": url, "done": False})
        after = (await owner.get(f"/digests/{digest_id}")).json()["plan"]

    assert [entry["done"] for entry in plan] == [False]
    # A second tick of the same line is the same tick.
    assert ticked.json() == again.json() == {"done": [url]}
    assert [entry["done"] for entry in reloaded] == [True]
    # Another reader cannot reach the issue, and a line the plan has not is no tick.
    assert stranger.status_code == 404
    assert elsewhere.status_code == 404
    assert unticked.json() == {"done": []}
    assert [entry["done"] for entry in after] == [False]
