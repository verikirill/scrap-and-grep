# ruff: noqa: F811  (fixtures are imported from test_accounts_api)
"""One build for both audiences: a specialist's digest and a management one
from the same profile, the second after the first, on its cached grades."""

import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from tests.test_accounts_api import api, database, profile_spec, register  # noqa: F401

pytestmark = pytest.mark.integration


async def test_both_audiences_are_built_one_after_the_other(api: str) -> None:
    from radar.worker import tasks

    async with register(api) as reader:
        profile = (await reader.post("/profiles", json=profile_spec())).json()
        response = await reader.post("/digests/both", json={"profile_id": profile["id"]})
        assert response.status_code == 202, response.text
        first, second = response.json()

    assert (first["audience"], second["audience"]) == ("specialist", "management")
    # One period for both, the week management reads.
    assert first["period_start"] == second["period_start"]
    queued: Any = tasks.build_digest.kiq
    queued.assert_awaited_once_with(first["id"], then=second["id"])


async def test_a_pair_needs_room_for_two_builds(api: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from radar.store import digests as digest_store

    monkeypatch.setattr(digest_store, "MAX_ACTIVE_PER_USER", 1)
    async with register(api) as reader:
        profile = (await reader.post("/profiles", json=profile_spec())).json()
        response = await reader.post("/digests/both", json={"profile_id": profile["id"]})

    assert response.status_code == 429


async def test_the_worker_queues_the_second_digest_after_the_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from radar.worker import tasks

    built: list[uuid.UUID] = []

    async def run(digest_id: uuid.UUID) -> None:
        built.append(digest_id)

    first, second = str(uuid.uuid4()), str(uuid.uuid4())
    monkeypatch.setattr(tasks, "run_digest", run)
    monkeypatch.setattr(tasks.build_digest, "kiq", AsyncMock())

    await tasks.build_digest(first, then=second)

    assert built == [uuid.UUID(first)]
    tasks.build_digest.kiq.assert_awaited_once_with(second)  # type: ignore[attr-defined]
