"""A poll of a source and the queue that hands it out: one poll at a time.

The ingest queue hands a message out again when its worker has not
acknowledged it for INGEST_IDLE_TIMEOUT_MS, and the worker acknowledges only
when the poll is done. A poll through the browser with full texts can run for
minutes, so the source's lock has to outlive the poll and the poll has to end
before the queue gives up on it; otherwise the second delivery takes the
expired lock and polls the same source again.
"""

import asyncio

import pytest

from radar.ingest import service
from radar.ingest.service import IngestReport
from radar.worker import tasks
from radar.worker.brokers import INGEST_IDLE_TIMEOUT_MS


def test_a_poll_ends_before_its_lock_and_the_lock_before_the_queue_gives_up() -> None:
    assert tasks.INGEST_RUN_LIMIT < service.LOCK_TTL_SECONDS < INGEST_IDLE_TIMEOUT_MS / 1000


def test_the_queue_waits_longer_than_a_poll_through_the_browser_takes() -> None:
    # Forty full texts through the browser, two tabs, half a minute each.
    assert tasks.INGEST_RUN_LIMIT >= 40 * 30 / 2


async def test_a_poll_past_its_limit_is_cut_and_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def endless(source_id: int, client: object, cache: object) -> IngestReport:
        await asyncio.sleep(60)
        return IngestReport(source_id, "ok")

    monkeypatch.setattr(tasks, "ingest_source", endless)
    monkeypatch.setattr(tasks, "INGEST_RUN_LIMIT", 0.05)

    result = await tasks.ingest_source_task(7)

    assert result == {"source_id": 7, "status": "cut", "new": 0}
