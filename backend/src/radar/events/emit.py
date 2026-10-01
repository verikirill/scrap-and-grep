"""Hand events to the stream that the writer takes into ClickHouse.

Emitting never raises and never waits for ClickHouse: an event is a record
of what happened, and losing one must not fail what happened.
"""

from redis.exceptions import RedisError

from radar.cache import get_redis
from radar.config import get_settings
from radar.events.model import Event, to_wire
from radar.logging import get_logger

log = get_logger(__name__)

# On the cache connection, without a TTL: Valkey evicts only keys that have
# one (volatile-lru), so the stream survives memory pressure.
STREAM = "radar:events"
FIELD = b"e"


def enabled() -> bool:
    return bool(get_settings().clickhouse_url)


async def emit(*events: Event) -> None:
    if not events or not enabled():
        return
    limit = get_settings().events_queue_max
    try:
        async with get_redis().pipeline(transaction=False) as pipe:
            for event in events:
                pipe.xadd(STREAM, {FIELD: to_wire(event)}, maxlen=limit, approximate=True)
            await pipe.execute()
    except RedisError as exc:
        log.warning("events_not_queued", count=len(events), error=type(exc).__name__)
