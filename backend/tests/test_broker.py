"""The queue must hand an abandoned task to another worker without new traffic.

Runs against a real Valkey or Redis (streams with consumer groups are the
point of the test) and is skipped when none is reachable:

    docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d valkey
"""

import asyncio
import os
import uuid

import pytest
from redis.asyncio import Redis
from redis.exceptions import RedisError
from taskiq import BrokerMessage

from radar.worker import brokers
from radar.worker.brokers import ReclaimingStreamBroker

BROKER_URL = os.environ.get("RADAR_TEST_BROKER_URL", "redis://127.0.0.1:6379/15")
IDLE_TIMEOUT_MS = 300


@pytest.mark.integration
async def test_idle_queue_still_reclaims_a_message_whose_worker_died(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe = Redis.from_url(BROKER_URL, socket_connect_timeout=1)
    try:
        await probe.ping()
    except RedisError, OSError:
        await probe.aclose()
        pytest.skip("no Valkey/Redis on RADAR_TEST_BROKER_URL")

    monkeypatch.setattr(brokers, "RECLAIM_EVERY_SECONDS", 0.05)
    queue = f"test:{uuid.uuid4().hex}"

    def make() -> ReclaimingStreamBroker:
        return ReclaimingStreamBroker(
            url=BROKER_URL,
            queue_name=queue,
            consumer_group_name="workers",
            idle_timeout=IDLE_TIMEOUT_MS,
            xread_block=50,
        )

    dying, survivor = make(), make()
    await dying.startup()
    await survivor.startup()
    try:
        await dying.kick(
            BrokerMessage(task_id="t1", task_name="build_digest", message=b"payload", labels={})
        )

        # The first worker takes the message and dies before acknowledging it.
        first = dying.listen()
        taken = await asyncio.wait_for(anext(first), timeout=5)
        await first.aclose()

        # Nothing else is enqueued. The second worker must still get it once
        # the idle timeout has passed.
        second = survivor.listen()
        reclaimed = await asyncio.wait_for(anext(second), timeout=5)
        await second.aclose()

        assert reclaimed.data == taken.data == b"payload"
    finally:
        await probe.delete(queue)
        await probe.aclose()
        await dying.shutdown()
        await survivor.shutdown()
