"""Events on their way from the API through Valkey into ClickHouse.

Runs against a real ClickHouse and Valkey and is skipped without them:

    docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d valkey clickhouse

A database of its own (radar_test) keeps the run away from development data.
"""

import os
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

pytestmark = pytest.mark.integration

CLICKHOUSE_URL = os.environ.get("RADAR_TEST_CLICKHOUSE_URL", "http://127.0.0.1:8123")
SETTINGS = {
    "RADAR_CLICKHOUSE_URL": CLICKHOUSE_URL,
    "RADAR_CLICKHOUSE_USER": os.environ.get("RADAR_TEST_CLICKHOUSE_USER", "radar"),
    "RADAR_CLICKHOUSE_PASSWORD": os.environ.get("RADAR_TEST_CLICKHOUSE_PASSWORD", "radar"),
    "RADAR_CLICKHOUSE_DATABASE": "radar_test",
    "RADAR_CACHE_URL": "redis://127.0.0.1:6379/15",
}


def _reset_caches() -> None:
    from radar.cache import get_cache, get_redis
    from radar.config import get_settings
    from radar.events import writer

    for cached in (get_settings, get_redis, get_cache):
        cached.cache_clear()
    writer._schema_ready = False


@pytest.fixture(scope="session")
def clickhouse_up() -> None:
    try:
        httpx.get(f"{CLICKHOUSE_URL}/ping", timeout=2).raise_for_status()
    except httpx.HTTPError:
        pytest.skip("ClickHouse is not reachable")


@pytest.fixture
def events_on(clickhouse_up: None, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Settings that send events to the test database."""
    for key, value in SETTINGS.items():
        monkeypatch.setenv(key, value)
    _reset_caches()
    yield
    _reset_caches()


@pytest.fixture
async def events(events_on: None) -> AsyncIterator[None]:
    """A migrated, empty events table and an empty stream."""
    from radar.cache import get_redis
    from radar.events import clickhouse

    try:
        await get_redis().flushdb()
    except RedisConnectionError:
        pytest.skip("Valkey is not reachable")
    await clickhouse.migrate()
    async with clickhouse.connect() as client:
        for table in ("events", "events_daily"):
            await client.command(f"TRUNCATE TABLE IF EXISTS {table}")
    yield
    await get_redis().aclose()


async def rows(where: str = "1", parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    from radar.events import clickhouse

    async with clickhouse.connect() as client:
        result = await client.query(
            f"SELECT * FROM events WHERE {where} ORDER BY ts, event_id",  # noqa: S608
            parameters=parameters,
        )
        return list(result.named_results())


def an_event(user_id: uuid.UUID | None = None, **fields: Any) -> Any:
    from radar.events import Event

    return Event(**{"event": "impression", "user_id": user_id or uuid.uuid4(), **fields})


async def test_events_reach_clickhouse_as_sent(events: None) -> None:
    from radar.events import emit
    from radar.events.writer import flush

    reader, snapshot = uuid.uuid4(), uuid.uuid4()
    await emit(
        an_event(
            reader,
            event="served",
            surface="feed",
            article_id=42,
            source_id=7,
            category="security",
            request_id=snapshot,
            position=3,
            slot="ranked",
            score=0.61,
            features={"interest": 0.8, "fresh": 0.02},
            variant="hand",
        ),
        an_event(reader, event="like", article_id=42, ts=datetime(2026, 9, 1, tzinfo=UTC)),
    )

    written = await flush()
    [like, served] = await rows()

    assert written == 2
    assert served["user_id"] == reader
    assert served["request_id"] == snapshot
    assert (served["position"], served["slot"], served["source_id"]) == (3, "ranked", 7)
    assert served["features"] == pytest.approx({"interest": 0.8, "fresh": 0.02})
    assert served["score"] == pytest.approx(0.61)
    assert like["event"] == "like"
    assert like["ts"].replace(tzinfo=UTC) == datetime(2026, 9, 1, tzinfo=UTC)


async def test_a_batch_retried_after_a_crash_is_not_doubled(
    events: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from radar.cache import get_redis
    from radar.events import emit
    from radar.events.emit import STREAM
    from radar.events.writer import flush

    await emit(*(an_event(article_id=index) for index in range(1, 6)))
    redis = get_redis()
    trim, crashed = redis.xtrim, []

    async def crash_once(*args: Any, **kwargs: Any) -> Any:
        if not crashed:
            crashed.append(True)
            raise RedisConnectionError("the writer died after the insert")
        return await trim(*args, **kwargs)

    # The insert goes through, the trim that should follow does not.
    monkeypatch.setattr(redis, "xtrim", crash_once)
    await flush()
    left_behind = await redis.xlen(STREAM)
    await flush()

    assert left_behind == 5
    assert len(await rows()) == 5
    assert await redis.xlen(STREAM) == 0


async def test_events_wait_in_the_stream_while_clickhouse_is_down(
    events: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from radar.cache import get_redis
    from radar.config import get_settings
    from radar.events import emit
    from radar.events.emit import STREAM
    from radar.events.writer import flush

    monkeypatch.setenv("RADAR_CLICKHOUSE_URL", "http://127.0.0.1:1")
    get_settings.cache_clear()
    await emit(an_event(), an_event())
    while_down = await flush()
    waiting = await get_redis().xlen(STREAM)

    monkeypatch.setenv("RADAR_CLICKHOUSE_URL", CLICKHOUSE_URL)
    get_settings.cache_clear()
    after = await flush()

    assert (while_down, waiting) == (0, 2)
    assert after == 2


async def test_a_malformed_entry_is_set_aside_and_the_rest_written(events: None) -> None:
    from radar.cache import get_redis
    from radar.events import emit
    from radar.events.emit import FIELD, STREAM
    from radar.events.writer import DEAD_LETTERS, backlog, flush

    await get_redis().xadd(STREAM, {FIELD: b'{"event": "like", "user_id": "not a uuid"}'})
    await emit(an_event())

    written = await flush()

    assert written == 1
    assert await backlog() == {"waiting": 0, "set_aside": 1}
    [(_, entry)] = await get_redis().xrange(DEAD_LETTERS)
    assert entry[b"reason"] == b"malformed"


async def test_nothing_is_queued_while_events_are_off(
    events: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from radar.cache import get_redis
    from radar.config import get_settings
    from radar.events import emit
    from radar.events.emit import STREAM
    from radar.events.writer import flush

    monkeypatch.setenv("RADAR_CLICKHOUSE_URL", "")
    get_settings.cache_clear()
    await emit(an_event())

    assert await get_redis().exists(STREAM) == 0
    assert await flush() == 0


async def test_forgetting_a_reader_deletes_their_events_even_those_still_waiting(
    events: None,
) -> None:
    from radar.events import emit
    from radar.events.writer import flush, forget

    leaving, staying = uuid.uuid4(), uuid.uuid4()
    await emit(an_event(leaving), an_event(staying))
    await flush()
    # Still in Valkey when the account goes.
    await emit(an_event(leaving))

    await forget([leaving])

    left = await rows()
    assert [row["user_id"] for row in left] == [staying]
