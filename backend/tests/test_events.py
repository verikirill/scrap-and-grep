# ruff: noqa: F811  (the database fixture is imported from the accounts tests)
"""Events on their way from the API through Valkey into ClickHouse.

Runs against real ClickHouse, Valkey and PostgreSQL (deleted readers are
noted there) and is skipped without them:

    docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres valkey clickhouse

Databases of their own (radar_test) keep the run away from development data.
"""

import os
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import numpy as np
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from tests.test_accounts_api import CACHE_URL, database  # noqa: F401  (fixture)

pytestmark = pytest.mark.integration

CLICKHOUSE_URL = os.environ.get("RADAR_TEST_CLICKHOUSE_URL", "http://127.0.0.1:8123")
SETTINGS = {
    "RADAR_CLICKHOUSE_URL": CLICKHOUSE_URL,
    "RADAR_CLICKHOUSE_USER": os.environ.get("RADAR_TEST_CLICKHOUSE_USER", "radar"),
    "RADAR_CLICKHOUSE_PASSWORD": os.environ.get("RADAR_TEST_CLICKHOUSE_PASSWORD", "radar"),
    "RADAR_CLICKHOUSE_DATABASE": "radar_test",
    "RADAR_CACHE_URL": CACHE_URL,
}


def _reset_caches() -> None:
    from radar.cache import get_cache, get_redis
    from radar.config import get_settings
    from radar.db import base
    from radar.events import writer
    from radar.ranker import model

    for cached in (get_settings, get_redis, get_cache, base.get_engine, base.get_sessionmaker):
        cached.cache_clear()
    writer._schema_ready = False
    model.forget()


@pytest.fixture(scope="session")
def clickhouse_up() -> None:
    try:
        httpx.get(f"{CLICKHOUSE_URL}/ping", timeout=2).raise_for_status()
    except httpx.HTTPError:
        pytest.skip("ClickHouse is not reachable")


@pytest.fixture
def events_on(
    clickhouse_up: None, database: None, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Settings that send events to the test database."""
    for key, value in SETTINGS.items():
        monkeypatch.setenv(key, value)
    _reset_caches()
    yield
    _reset_caches()


@pytest.fixture
async def events(events_on: None) -> AsyncIterator[None]:
    """A migrated, empty events table and an empty stream."""
    from sqlalchemy import delete

    from radar.cache import get_redis
    from radar.db import base, session_scope
    from radar.db.models import ForgottenReader, RankerModel
    from radar.events import clickhouse

    try:
        await get_redis().flushdb()
    except RedisConnectionError:
        pytest.skip("Valkey is not reachable")
    await clickhouse.migrate()
    async with clickhouse.connect() as client:
        for table in ("events", "events_daily"):
            await client.command(f"TRUNCATE TABLE {table}")
    async with session_scope() as session:
        await session.execute(delete(ForgottenReader))
        await session.execute(delete(RankerModel))
    yield
    await get_redis().aclose()
    await base.get_engine().dispose()


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
    from radar.config import get_settings
    from radar.events import emit
    from radar.events.writer import MAX_ATTEMPTS, backlog, flush

    monkeypatch.setenv("RADAR_CLICKHOUSE_URL", "http://127.0.0.1:1")
    get_settings.cache_clear()
    await emit(an_event(), an_event())
    # Longer than any number of attempts: an outage is not a refusal.
    while_down = [await flush() for _ in range(MAX_ATTEMPTS + 1)]
    waiting = await backlog()

    monkeypatch.setenv("RADAR_CLICKHOUSE_URL", CLICKHOUSE_URL)
    get_settings.cache_clear()
    after = await flush()

    assert set(while_down) == {0}
    assert waiting == {"waiting": 2, "set_aside": 0}
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
    assert entry[b"reason"] == b"unreadable"


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


async def test_a_forgotten_reader_loses_stored_events_and_those_still_coming(
    events: None,
) -> None:
    from radar.db import session_scope
    from radar.db.models import ForgottenReader
    from radar.events import emit
    from radar.events.writer import flush

    leaving, staying = uuid.uuid4(), uuid.uuid4()
    await emit(an_event(leaving), an_event(staying))
    await flush()
    # Still in Valkey when the account goes.
    await emit(an_event(leaving))
    async with session_scope() as session:
        session.add(ForgottenReader(user_id=leaving))

    await flush()
    # A request that was in flight when the account went.
    await emit(an_event(leaving))
    await flush()

    left = await rows()
    assert [row["user_id"] for row in left] == [staying]
    async with session_scope() as session:
        tombstone = await session.get(ForgottenReader, leaving)
    assert tombstone is not None
    assert tombstone.purged_at is not None


async def test_nightly_training_learns_from_the_events_and_switches_the_model_on(
    events: None,
) -> None:
    from radar.events import emit
    from radar.events.writer import flush
    from radar.ranker import model
    from radar.ranker.train import train

    # Four hundred feed lists over two weeks. Readers open and like fresh
    # articles wherever they are; the hand score is noise.
    rng = np.random.default_rng(3)
    now = datetime.now(UTC)
    readers = [uuid.uuid4() for _ in range(30)]
    for index in range(400):
        served_at = now - timedelta(days=14) + timedelta(days=14) * index / 400
        reader, snapshot = readers[index % len(readers)], uuid.uuid4()
        batch = []
        for position in range(1, 21):
            fresh, article = float(rng.random()), index * 100 + position
            placed = {"surface": "feed", "article_id": article, "request_id": snapshot}
            features = {"score": float(rng.random()), "fresh": fresh, "confidence": 0.5}
            batch.append(
                an_event(
                    reader,
                    event="served",
                    ts=served_at,
                    position=position,
                    features=features,
                    **placed,
                )
            )
            seen_at = served_at + timedelta(minutes=position)
            batch.append(an_event(reader, ts=seen_at, position=position, **placed))
            if fresh > 0.6:
                batch.append(an_event(reader, event="open", ts=seen_at, **placed))
            if fresh > 0.8:
                batch.append(an_event(reader, event="like", ts=seen_at, **placed))
        await emit(*batch)
    await flush(budget_seconds=120)

    run = await train(now)
    active = await model.active()

    assert run.status == "active", run.note
    assert run.metrics["model_ndcg"] > run.metrics["hand_ndcg"]
    assert active is not None
    assert active.version == run.version
