"""Take the stream of events into ClickHouse in batches.

One writer at a time (a Valkey lock), every minute. A batch is the oldest
entries of the stream; its first and last ids are noted before the insert and
the entries are trimmed after it. If the writer dies in between, the next run
finds the note, reads the same range and inserts it with the same
deduplication token: ClickHouse drops the repeat, nothing is doubled.

While ClickHouse is down or refuses the connection, entries stay in the
stream and the app goes on; any answer from the server is retried, however
long it takes. Only an entry that cannot be read, or a batch the client
cannot even encode, is moved to a dead-letter stream, so one bad event
cannot hold up the rest.

The same run forgets deleted readers (see `ForgottenReader`): their events
still on the way are dropped, the stored ones deleted.
"""

import asyncio
import time
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import orjson
from clickhouse_connect.driver.asyncclient import AsyncClient
from clickhouse_connect.driver.exceptions import DatabaseError
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import delete, select, update
from sqlalchemy.exc import SQLAlchemyError

from radar.cache import get_cache, get_redis
from radar.db import session_scope
from radar.db.models import ForgottenReader
from radar.events import clickhouse
from radar.events.emit import FIELD, STREAM, enabled
from radar.events.model import COLUMNS, from_wire
from radar.logging import get_logger

log = get_logger(__name__)

BATCH = 5_000
DEAD_LETTERS = "radar:events:dead"
DEAD_LETTERS_MAX = 10_000
# Set-aside entries still name their reader; they go after a week.
DEAD_LETTERS_TTL = 7 * 24 * 3600
# A batch the client failed to encode this many times in a row is set aside.
MAX_ATTEMPTS = 3
# Without a TTL, like the stream: Valkey never evicts it under memory pressure.
_PENDING = "radar:events:pending"
_LOCK = "events-writer"
_LOCK_TTL = 300
# How long a deleted reader's events are still dropped on arrival: requests
# in flight when the account went may emit a few more.
FORGET_GRACE = timedelta(days=1)
_USER_ID = COLUMNS.index("user_id")

Entries = list[tuple[bytes, bytes]]

_schema_ready = False


class _Unencodable(Exception):
    """The client could not turn the batch into an insert; it will be retried."""


def _after(entry_id: bytes) -> str:
    """The smallest stream id greater than `entry_id`."""
    ms, seq = entry_id.decode().split("-")
    return f"{ms}-{int(seq) + 1}"


async def _ensure_schema() -> None:
    global _schema_ready
    if not _schema_ready:
        await clickhouse.migrate()
        _schema_ready = True


async def _next_batch(redis: Redis) -> tuple[Entries, dict[str, Any]]:
    """The entries to write and the note about them (range and failed attempts)."""
    raw = await redis.get(_PENDING)
    if raw is not None:
        note: dict[str, Any] = orjson.loads(raw)
        rows: Any = await redis.xrange(STREAM, note["first"], note["last"])
        if rows:
            return [(entry_id, fields[FIELD]) for entry_id, fields in rows], note
        await redis.delete(_PENDING)
    rows = await redis.xrange(STREAM, "-", "+", count=BATCH)
    entries = [(entry_id, fields[FIELD]) for entry_id, fields in rows]
    if not entries:
        return [], {}
    note = {"first": entries[0][0].decode(), "last": entries[-1][0].decode(), "attempts": 0}
    await redis.set(_PENDING, orjson.dumps(note))
    return entries, note


async def _set_aside(redis: Redis, entries: Entries, reason: str) -> None:
    async with redis.pipeline(transaction=False) as pipe:
        for _, raw in entries:
            pipe.xadd(
                DEAD_LETTERS,
                {FIELD: raw, b"reason": reason.encode()},
                maxlen=DEAD_LETTERS_MAX,
                approximate=True,
            )
        pipe.expire(DEAD_LETTERS, DEAD_LETTERS_TTL)
        await pipe.execute()


async def _write_batch(
    client: AsyncClient,
    redis: Redis,
    entries: Entries,
    note: dict[str, Any],
    forgotten: frozenset[uuid.UUID],
) -> int:
    rows, good, broken = [], [], []
    for entry in entries:
        try:
            row = from_wire(entry[1])
        except ValueError:
            broken.append(entry)
            continue
        good.append(entry)
        if row[_USER_ID] not in forgotten:
            rows.append(row)
    if rows:
        try:
            # The token comes from the note, not from what was read: entries
            # trimmed off the head of the range must not change it.
            await client.insert(
                "events",
                rows,
                column_names=list(COLUMNS),
                settings={"insert_deduplication_token": f"{note['first']}:{note['last']}"},
            )
        except DatabaseError:
            # The server answered or could not be reached: either way the
            # events wait for the next run.
            raise
        except Exception as exc:
            attempts = int(note.get("attempts", 0)) + 1
            if attempts < MAX_ATTEMPTS:
                await redis.set(_PENDING, orjson.dumps(note | {"attempts": attempts}))
                raise _Unencodable(f"{type(exc).__name__}: {exc}"[:300]) from exc
            log.error("events_batch_set_aside", count=len(rows), error=str(exc)[:300])
            broken, rows = broken + good, []
    if broken:
        log.warning("events_set_aside", count=len(broken))
        await _set_aside(redis, broken, "unreadable")
    await redis.xtrim(STREAM, minid=_after(entries[-1][0]), approximate=False)
    await redis.delete(_PENDING)
    return len(rows)


async def _forgotten() -> tuple[frozenset[uuid.UUID], list[uuid.UUID]]:
    """Readers whose events are dropped, and those still to be deleted."""
    async with session_scope() as session:
        rows = (await session.execute(select(ForgottenReader))).scalars().all()
    return (
        frozenset(row.user_id for row in rows),
        [row.user_id for row in rows if row.purged_at is None],
    )


async def _purge(client: AsyncClient, user_ids: Sequence[uuid.UUID]) -> None:
    """Delete the stored events of deleted readers and note that it is done."""
    if user_ids:
        await client.command(
            "DELETE FROM events WHERE user_id IN %(ids)s",
            parameters={"ids": [str(user_id) for user_id in user_ids]},
        )
    now = datetime.now(UTC)
    async with session_scope() as session:
        if user_ids:
            await session.execute(
                update(ForgottenReader)
                .where(ForgottenReader.user_id.in_(user_ids))
                .values(purged_at=now)
            )
        # Forgotten for a day: by now no request of theirs is still running.
        await session.execute(
            delete(ForgottenReader).where(
                ForgottenReader.purged_at.is_not(None),
                ForgottenReader.deleted_at < now - FORGET_GRACE,
            )
        )
    if user_ids:
        log.info("events_forgotten", readers=len(user_ids))


async def _run(budget_seconds: float) -> int:
    global _schema_ready
    redis = get_redis()
    forgotten, to_purge = await _forgotten()
    written = 0
    started = time.monotonic()
    await _ensure_schema()
    try:
        async with clickhouse.connect() as client:
            while time.monotonic() - started < budget_seconds:
                entries, note = await _next_batch(redis)
                if not entries:
                    break
                written += await _write_batch(client, redis, entries, note, forgotten)
            # After the stream: nothing of theirs is left on the way.
            await _purge(client, to_purge)
    except DatabaseError:
        # A table dropped by hand comes back with the next run.
        _schema_ready = False
        raise
    return written


async def flush(*, budget_seconds: float = 45.0) -> int:
    """Write what the stream holds, batch after batch, for at most `budget_seconds`,
    then delete the events of deleted readers.

    Returns the number of events written. Does nothing while events are off,
    and gives up quietly (the events wait) while ClickHouse is unreachable.
    """
    if not enabled():
        return 0
    async with get_cache().lock(_LOCK, _LOCK_TTL) as acquired:
        if not acquired:
            return 0
        try:
            written = await _run(budget_seconds)
        except (_Unencodable, DatabaseError, RedisError, SQLAlchemyError, OSError) as exc:
            log.warning("events_not_written", error=f"{type(exc).__name__}: {exc}"[:300])
            return 0
    if written:
        log.info("events_written", count=written)
    return written


async def backlog() -> dict[str, int]:
    """How many events wait for ClickHouse, and how many were set aside."""
    redis = get_redis()
    try:
        waiting, dead = await asyncio.gather(redis.xlen(STREAM), redis.xlen(DEAD_LETTERS))
    except RedisError:
        return {"waiting": -1, "set_aside": -1}
    return {"waiting": int(waiting), "set_aside": int(dead)}
