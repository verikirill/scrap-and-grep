"""Task brokers on Redis Streams.

Four queues, four worker pools. Feed fetching is I/O-bound and cheap, digest
building is bound by the model server, and the profile queue serves a reader
who is waiting at the screen: a resume being analysed during sign-up must not
stand behind a batch of feeds or a long digest. Videos take minutes of GPU and
CPU in other services and get a queue of their own. Each pool scales on its
own.

Streams with consumer groups give at-least-once delivery: a message is
acknowledged after the task finishes, and a message whose worker died is
claimed by another worker once it has been idle for `idle_timeout`.
"""

import time
from collections.abc import AsyncGenerator
from typing import Any

from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from taskiq import AckableMessage, TaskiqEvents, TaskiqScheduler, TaskiqState
from taskiq.middlewares import SmartRetryMiddleware
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_redis import RedisStreamBroker

from radar.config import get_settings
from radar.logging import configure_logging

# Must exceed the longest legitimate run of a task in the queue, otherwise a
# slow task would be handed to a second worker while the first still runs.
_settings = get_settings()

# A poll through the browser with forty full texts runs for minutes; sources
# are polled every 15 minutes, so a poll that went quiet that long is dead.
INGEST_IDLE_TIMEOUT_MS = 15 * 60 * 1000
PROFILE_IDLE_TIMEOUT_MS = 6 * 60 * 1000
# Script, voice and render of one video, each with its own timeout, in a row.
MEDIA_IDLE_TIMEOUT_MS = (
    int(
        _settings.llm_timeout_seconds
        + _settings.tts_timeout_seconds
        + _settings.shorts_timeout_seconds
    )
    + 5 * 60
) * 1000
DIGEST_IDLE_TIMEOUT_MS = _settings.digest_task_timeout_seconds * 1000
STREAM_MAX_LENGTH = 100_000
RECLAIM_EVERY_SECONDS = 10.0
BROKER_HEALTH_CHECK_SECONDS = 30
BROKER_RETRIES = 3


class ReclaimingStreamBroker(RedisStreamBroker):
    """Stream broker that takes over abandoned messages even on an idle queue.

    taskiq-redis 1.2.4 looks for unacknowledged messages only right after it
    has received a new one (`if not fetched: continue` in its `listen`). A task
    whose worker died therefore waits until somebody happens to enqueue
    another task, which on a quiet queue means indefinitely. Found by killing
    a worker mid-digest: the message sat in the pending list well past its
    idle timeout. Here the check runs on a timer, new messages or not.

    XAUTOCLAIM is atomic, so several workers may call it at once: the first
    one gets the message and resets its idle time.
    """

    async def listen(self) -> AsyncGenerator[AckableMessage]:
        streams = {self.queue_name: ">", **self.additional_streams}
        last_reclaim = 0.0
        async with Redis(connection_pool=self.connection_pool) as connection:
            while True:
                # redis-py types stream replies loosely; the shape is
                # [(stream, [(message_id, {field: value})])].
                fetched: Any = await connection.xreadgroup(
                    self.consumer_group_name,
                    self.consumer_name,
                    streams,  # type: ignore[arg-type]
                    block=self.block,
                    noack=False,
                    count=self.count,
                )
                for stream, messages in fetched or []:
                    for message_id, message in messages:
                        yield AckableMessage(
                            data=message[b"data"],
                            ack=self._ack_generator(id=message_id, queue_name=stream),
                        )
                if time.monotonic() - last_reclaim < RECLAIM_EVERY_SECONDS:
                    continue
                last_reclaim = time.monotonic()
                for stream in streams:
                    claimed: Any = await connection.xautoclaim(
                        name=stream,
                        groupname=self.consumer_group_name,
                        consumername=self.consumer_name,
                        min_idle_time=self.idle_timeout,
                        count=self.unacknowledged_batch_size,
                    )
                    for message_id, message in claimed[1]:
                        yield AckableMessage(
                            data=message[b"data"],
                            ack=self._ack_generator(id=message_id, queue_name=stream),
                        )


def _broker(queue: str, idle_timeout_ms: int) -> ReclaimingStreamBroker:
    broker = ReclaimingStreamBroker(
        url=_settings.broker_url,
        queue_name=f"radar:{queue}",
        consumer_group_name=f"radar-{queue}",
        idle_timeout=idle_timeout_ms,
        maxlen=STREAM_MAX_LENGTH,
        # After a Valkey restart the pool still holds connections the server
        # has closed, and redis-py does not retry by default: the first task
        # sent after the restart failed. A connection idle for a while is now
        # checked before use, and a broken one is replaced and the command
        # retried. A task sent twice is harmless: every task is idempotent.
        health_check_interval=BROKER_HEALTH_CHECK_SECONDS,
        retry=Retry(ExponentialBackoff(cap=1.0, base=0.05), BROKER_RETRIES),
        retry_on_error=[RedisConnectionError, RedisTimeoutError],
    ).with_middlewares(
        SmartRetryMiddleware(
            default_retry_count=3,
            default_delay=5,
            use_jitter=True,
            use_delay_exponent=True,
            max_delay_exponent=120,
        )
    )

    @broker.on_event(TaskiqEvents.WORKER_STARTUP)
    async def _startup(state: TaskiqState) -> None:
        configure_logging(_settings.log_level, json=_settings.log_json)

    @broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
    async def _shutdown(state: TaskiqState) -> None:
        from radar.db import get_engine

        await get_engine().dispose()

    return broker


ingest_broker = _broker("ingest", INGEST_IDLE_TIMEOUT_MS)
digest_broker = _broker("digest", DIGEST_IDLE_TIMEOUT_MS)
profile_broker = _broker("profile", PROFILE_IDLE_TIMEOUT_MS)
media_broker = _broker("media", MEDIA_IDLE_TIMEOUT_MS)

scheduler = TaskiqScheduler(broker=ingest_broker, sources=[LabelScheduleSource(ingest_broker)])
