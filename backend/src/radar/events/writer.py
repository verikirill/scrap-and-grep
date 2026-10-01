"""Take the stream of events into ClickHouse in batches.

One writer at a time (a Valkey lock). A batch is the oldest entries of the
stream; its first and last ids are noted before the insert and the entries
are trimmed after it. If the writer dies in between, the next run finds the
note, reads exactly the same entries and inserts them with the same
deduplication token: ClickHouse drops the repeat, nothing is doubled.

While ClickHouse is down the entries stay in the stream and the app goes on.
An entry that cannot be read, or a batch the server keeps refusing for a
reason other than being unreachable, is moved to a dead-letter stream, so one
bad event cannot hold up the rest.
"""

import asyncio
import time
import uuid
from collections.abc import Sequence
from typing import Any

from clickhouse_connect.driver.asyncclient import AsyncClient
from clickhouse_connect.driver.exceptions import OperationalError
from redis.asyncio import Redis
from redis.exceptions import RedisError

from radar.cache import Cache, get_cache, get_redis
from radar.events import clickhouse
from radar.events.emit import FIELD, STREAM, enabled
from radar.events.model import COLUMNS, from_wire
from radar.logging import get_logger

log = get_logger(__name__)

BATCH = 5_000
DEAD_LETTERS = "radar:events:dead"
DEAD_LETTERS_MAX = 10_000
# A batch the server refused this many times in a row is set aside.
MAX_ATTEMPTS = 5
_PENDING = "events:pending"
_LOCK = "events-writer"
_LOCK_TTL = 300
_PENDING_TTL = 7 * 24 * 3600

Entries = list[tuple[bytes, bytes]]

_schema_ready = False


class WriterBusy(Exception):
    """Another process is writing the stream right now."""


class _Refused(Exception):
    """ClickHouse answered, and said no; the batch will be tried again."""


def _after(entry_id: bytes) -> str:
    """The smallest stream id greater than `entry_id`."""
    ms, seq = entry_id.decode().split("-")
    return f"{ms}-{int(seq) + 1}"


async def _ensure_schema() -> None:
    global _schema_ready
    if not _schema_ready:
        await clickhouse.migrate()
        _schema_ready = True


async def _next_batch(redis: Redis, cache: Cache) -> tuple[Entries, int]:
    """The entries of the batch to write and how many times it was tried."""
    pending = await cache.get_json(_PENDING)
    if pending is not None:
        rows: Any = await redis.xrange(STREAM, pending["first"], pending["last"])
        if rows:
            return [(entry_id, fields[FIELD]) for entry_id, fields in rows], pending["attempts"]
        await cache.delete(_PENDING)
    rows = await redis.xrange(STREAM, "-", "+", count=BATCH)
    return [(entry_id, fields[FIELD]) for entry_id, fields in rows], 0


async def _set_aside(redis: Redis, entries: Entries, reason: str) -> None:
    async with redis.pipeline(transaction=False) as pipe:
        for _, raw in entries:
            pipe.xadd(
                DEAD_LETTERS,
                {FIELD: raw, b"reason": reason.encode()},
                maxlen=DEAD_LETTERS_MAX,
                approximate=True,
            )
        await pipe.execute()


async def _write_batch(
    client: AsyncClient, redis: Redis, cache: Cache, entries: Entries, tried: int
) -> int:
    first, last = entries[0][0].decode(), entries[-1][0].decode()
    await cache.set_json(
        _PENDING, {"first": first, "last": last, "attempts": tried + 1}, _PENDING_TTL
    )
    rows, good, broken = [], [], []
    for entry in entries:
        try:
            rows.append(from_wire(entry[1]))
            good.append(entry)
        except ValueError:
            broken.append(entry)
    if broken:
        log.warning("events_malformed", count=len(broken))
        await _set_aside(redis, broken, "malformed")
    if rows:
        try:
            await client.insert(
                "events",
                rows,
                column_names=list(COLUMNS),
                settings={"insert_deduplication_token": f"{first}:{last}"},
            )
        except OperationalError:
            raise
        except Exception as exc:
            if tried + 1 < MAX_ATTEMPTS:
                raise _Refused(f"{type(exc).__name__}: {exc}"[:300]) from exc
            log.error("events_batch_set_aside", count=len(rows), error=str(exc)[:300])
            await _set_aside(redis, good, "refused")
            rows = []
    await redis.xtrim(STREAM, minid=_after(entries[-1][0]), approximate=False)
    await cache.delete(_PENDING)
    return len(rows)


async def _drain(budget_seconds: float) -> int:
    cache, redis = get_cache(), get_redis()
    written = 0
    started = time.monotonic()
    await _ensure_schema()
    async with clickhouse.connect() as client:
        while time.monotonic() - started < budget_seconds:
            entries, tried = await _next_batch(redis, cache)
            if not entries:
                break
            written += await _write_batch(client, redis, cache, entries, tried)
    return written


async def flush(*, budget_seconds: float = 45.0) -> int:
    """Write what the stream holds, batch after batch, for at most `budget_seconds`.

    Returns the number of events written. Does nothing while events are off,
    and gives up quietly (the events wait) while ClickHouse is unreachable.
    """
    if not enabled():
        return 0
    async with get_cache().lock(_LOCK, _LOCK_TTL) as acquired:
        if not acquired:
            return 0
        try:
            written = await _drain(budget_seconds)
        except (_Refused, OperationalError, RedisError, OSError) as exc:
            log.warning("events_not_written", error=f"{type(exc).__name__}: {exc}"[:300])
            return 0
    if written:
        log.info("events_written", count=written)
    return written


async def forget(user_ids: Sequence[uuid.UUID]) -> None:
    """Delete everything recorded about these readers.

    Writes the stream out first, under the writer's lock, so an event still
    waiting there cannot be inserted after the delete. Raises while another
    writer runs or ClickHouse is unreachable: the calling task retries.
    """
    if not user_ids or not enabled():
        return
    async with get_cache().lock(_LOCK, _LOCK_TTL) as acquired:
        if not acquired:
            raise WriterBusy
        await _drain(budget_seconds=float(_LOCK_TTL // 2))
        async with clickhouse.connect() as client:
            await client.command(
                "DELETE FROM events WHERE user_id IN %(ids)s",
                parameters={"ids": [str(user_id) for user_id in user_ids]},
            )


async def backlog() -> dict[str, int]:
    """How many events wait for ClickHouse, and how many were set aside."""
    redis = get_redis()
    try:
        waiting, dead = await asyncio.gather(redis.xlen(STREAM), redis.xlen(DEAD_LETTERS))
    except RedisError:
        return {"waiting": -1, "set_aside": -1}
    return {"waiting": int(waiting), "set_aside": int(dead)}
