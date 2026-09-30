"""Task brokers on Redis Streams.

Two queues, two worker pools: feed fetching is I/O-bound and cheap, digest
building is bound by the model server. Keeping them apart means a burst of
digest requests cannot delay ingestion, and each pool scales on its own.

Streams with consumer groups give at-least-once delivery: a message is
acknowledged after the task finishes, and a message whose worker died is
claimed by another worker once it has been idle for `idle_timeout`.
"""

from taskiq import TaskiqEvents, TaskiqScheduler, TaskiqState
from taskiq.middlewares import SmartRetryMiddleware
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_redis import RedisStreamBroker

from radar.config import get_settings
from radar.logging import configure_logging

# Must exceed the longest legitimate run of a task in the queue, otherwise a
# slow task would be handed to a second worker while the first still runs.
_settings = get_settings()

INGEST_IDLE_TIMEOUT_MS = 5 * 60 * 1000
DIGEST_IDLE_TIMEOUT_MS = _settings.digest_task_timeout_seconds * 1000
STREAM_MAX_LENGTH = 100_000


def _broker(queue: str, idle_timeout_ms: int) -> RedisStreamBroker:
    broker = RedisStreamBroker(
        url=_settings.broker_url,
        queue_name=f"radar:{queue}",
        consumer_group_name=f"radar-{queue}",
        idle_timeout=idle_timeout_ms,
        unacknowledged_lock_timeout=60.0,
        maxlen=STREAM_MAX_LENGTH,
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

scheduler = TaskiqScheduler(broker=ingest_broker, sources=[LabelScheduleSource(ingest_broker)])
