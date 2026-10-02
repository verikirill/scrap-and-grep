"""Accounts, ownership, resume and feed through the HTTP API on a real PostgreSQL.

    docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres valkey

These are the checks that only mean something against the database: that one
reader cannot reach another reader's rows, that a deleted account leaves
nothing behind, that an uploaded file is gone once it has been read. Skipped
when PostgreSQL is not reachable. A separate database is created for the run,
so the development data is not touched.
"""

import os
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import httpx
import psycopg
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import undefer

pytestmark = pytest.mark.integration

ADMIN_DSN = os.environ.get(
    "RADAR_TEST_ADMIN_DSN", "postgresql://radar:radar@127.0.0.1:5432/postgres"
)
TEST_DB = "radar_test"
PASSWORD = "correct-horse-battery"


def _database_ready() -> bool:
    try:
        with psycopg.connect(ADMIN_DSN, autocommit=True, connect_timeout=2) as connection:
            exists = connection.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,)
            ).fetchone()
            if exists is None:
                connection.execute(f'CREATE DATABASE "{TEST_DB}"')
    except psycopg.OperationalError:
        return False
    return True


@pytest.fixture(scope="session")
def database() -> Iterator[None]:
    """A migrated, empty database and settings that point at it."""
    if not _database_ready():
        pytest.skip("PostgreSQL is not reachable")
    overrides = {
        "RADAR_DATABASE_URL": ADMIN_DSN.replace("postgresql://", "postgresql+psycopg://").rsplit(
            "/", 1
        )[0]
        + f"/{TEST_DB}",
        "RADAR_DB_DISABLE_PREPARED_STATEMENTS": "false",
        # Database 15 keeps the run away from the development cache and queues.
        "RADAR_CACHE_URL": "redis://127.0.0.1:6379/15",
        "RADAR_EMBEDDING_PROVIDER": "hashing",
        "RADAR_LLM_PROVIDER": "heuristic",
        "RADAR_DOCPARSER_URL": "",
        "RADAR_DEMO_LOGIN": "true",
        "RADAR_AUTH_RATE_LIMIT_PER_MINUTE": "1000",
        "RADAR_RESUME_RATE_LIMIT_PER_MINUTE": "1000",
    }
    previous = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)

    from radar.config import get_settings

    get_settings.cache_clear()
    from alembic import command

    from radar.cli import _alembic_config

    command.upgrade(_alembic_config(), "head")
    yield
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()


@pytest.fixture
async def api(database: None, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[str]:
    """Base URL of the app, with a clean database and no task queue behind it."""
    from radar.ai.factory import get_embedder, get_intelligence
    from radar.cache import get_cache, get_redis
    from radar.db import base, session_scope
    from radar.db.models import Article, Source, User
    from radar.seed import seed_defaults
    from radar.worker import tasks

    for cached in (base.get_engine, base.get_sessionmaker, get_redis, get_cache):
        cached.cache_clear()
    get_embedder.cache_clear()
    get_intelligence.cache_clear()
    # Tasks are not sent anywhere: the tests call the task bodies themselves.
    for task in (
        tasks.process_resume,
        tasks.refresh_taste,
        tasks.build_digest,
        tasks.measure_articles,
        tasks.adapt_profiles,
    ):
        monkeypatch.setattr(task, "kiq", AsyncMock())

    from sqlalchemy import delete

    async with session_scope() as session:
        await session.execute(delete(User).where(User.is_demo.is_(False)))
        await session.execute(delete(Article))
        await session.execute(delete(Source))
    # The example profiles guests start with, as a fresh stack has them.
    async with session_scope() as session:
        await seed_defaults(session)
    # The cache is optional for these tests: without it sessions are read from
    # the database and rate limits are not counted.
    with suppress(Exception):
        await get_redis().flushdb()
    yield "http://radar.test/api/v1"
    await base.get_engine().dispose()
    await get_redis().aclose()
    for cached in (base.get_engine, base.get_sessionmaker, get_redis, get_cache):
        cached.cache_clear()


def client(base_url: str) -> httpx.AsyncClient:
    from radar.api.app import app

    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=base_url)


@asynccontextmanager
async def register(base_url: str, name: str = "reader") -> AsyncIterator[httpx.AsyncClient]:
    """A signed-in reader with a fresh account."""
    async with client(base_url) as reader:
        response = await reader.post(
            "/auth/register",
            json={
                "email": f"{name}.{uuid.uuid4().hex[:8]}@example.org",
                "password": PASSWORD,
                "display_name": name,
            },
        )
        assert response.status_code == 201, response.text
        yield reader


def profile_spec(name: str = "Сети") -> dict[str, object]:
    return {
        "name": name,
        "role": "Инженер",
        "interests": [{"id": "net", "title": "Сети", "keywords": ["маршрутизатор", "VPN"]}],
    }


async def seed_articles() -> dict[str, int]:
    """Six articles on two themes, embedded with the offline embedder."""
    from radar.ai.factory import get_embedder
    from radar.db import session_scope
    from radar.db.models import Source
    from radar.ingest.service import embed_pending
    from radar.store.articles import NewArticle, insert_new
    from radar.text import content_hash

    titles = {
        "vpn": "Уязвимость в VPN-шлюзах: маршрутизатор принимает чужие пакеты",
        "router": "Обновление прошивки закрывает дыру: маршрутизатор и VPN под ударом",
        "router2": "Маршрутизатор уровня ядра: как настроить VPN между площадками",
        "soup": "Рецепт борща: свёкла, капуста и говяжий бульон",
        "soup2": "Как варить бульон для борща и щей из капусты",
        "cake": "Торт на сметане: бисквит, крем и ягоды",
    }
    now = datetime.now(UTC)
    async with session_scope() as session:
        source = Source(
            slug="test", name="Тест", feed_url="https://example.org/feed", category="it"
        )
        session.add(source)
        await session.flush()
        ids = await insert_new(
            session,
            source.id,
            [
                NewArticle(
                    url=f"https://example.org/{key}",
                    title=title,
                    summary=title,
                    content=None,
                    author=None,
                    tags=(),
                    language="ru",
                    published_at=now - timedelta(hours=index + 1),
                    content_hash=content_hash(title, title),
                )
                for index, (key, title) in enumerate(titles.items())
            ],
        )
    await embed_pending(get_embedder())
    return dict(zip(titles, ids, strict=True))


async def test_session_lifecycle(api: str) -> None:
    async with register(api, "anna") as reader:
        cookie = next(iter(reader.cookies.jar))
        assert cookie.name == "radar_session"
        assert "HttpOnly" in cookie._rest  # type: ignore[attr-defined]
        assert (await reader.get("/auth/me")).json()["display_name"] == "anna"

        assert (await reader.post("/auth/logout")).status_code == 204
        assert (await reader.get("/auth/me")).json() is None
        assert (await reader.get("/profiles")).status_code == 401


async def test_wrong_password_and_unknown_address_look_the_same(api: str) -> None:
    async with register(api, "boris") as reader:
        email = (await reader.get("/auth/me")).json()["email"]
    async with client(api) as visitor:
        wrong = await visitor.post(
            "/auth/login", json={"email": email, "password": "not-the-password"}
        )
        unknown = await visitor.post(
            "/auth/login", json={"email": "nobody@example.org", "password": "not-the-password"}
        )
        again = await visitor.post(
            "/auth/register",
            json={"email": email.upper(), "password": PASSWORD, "display_name": "boris"},
        )
        ok = await visitor.post("/auth/login", json={"email": email.upper(), "password": PASSWORD})

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert again.status_code == 409
    assert ok.status_code == 200


async def test_a_reader_cannot_reach_another_readers_profiles_or_digests(api: str) -> None:
    from radar.db import session_scope
    from radar.domain import ProfileSpec
    from radar.store import digests as digest_store

    async with register(api, "owner") as owner, register(api, "other") as other:
        profile = (await owner.post("/profiles", json=profile_spec())).json()
        now = datetime.now(UTC)
        async with session_scope() as session:
            digest = await digest_store.create(
                session,
                user_id=uuid.UUID((await owner.get("/auth/me")).json()["id"]),
                profile_id=uuid.UUID(profile["id"]),
                profile=ProfileSpec.model_validate(profile["spec"]),
                profile_version=1,
                period_start=now - timedelta(days=7),
                period_end=now,
            )
        digest_id = str(digest.id)

        assert (await owner.get(f"/digests/{digest_id}")).status_code == 200
        assert (await other.get("/profiles")).json() == []
        assert (await other.get("/digests")).json() == []
        attempts = [
            await other.get(f"/profiles/{profile['id']}"),
            await other.put(f"/profiles/{profile['id']}", json=profile_spec("Чужое")),
            await other.delete(f"/profiles/{profile['id']}"),
            await other.post("/digests", json={"profile_id": profile["id"]}),
            await other.get(f"/digests/{digest_id}"),
            await other.get(f"/digests/{digest_id}/export.md"),
            await other.get(f"/digests/{digest_id}/export.docx"),
            await other.get("/digests/compare", params={"base": digest_id, "other": digest_id}),
            await other.delete(f"/digests/{digest_id}"),
        ]
        events = await other.get(f"/digests/{digest_id}/events")

        # "Not found", never "forbidden": the answer does not confirm the id exists.
        assert [response.status_code for response in attempts] == [404] * len(attempts)
        assert "event: error" in events.text
        assert "progress" not in events.text
        # The owner's rows are intact.
        assert (await owner.get(f"/profiles/{profile['id']}")).json()["spec"]["name"] == "Сети"
        assert (await owner.get(f"/digests/{digest_id}")).status_code == 200


async def test_only_an_administrator_changes_the_source_catalogue(api: str) -> None:
    from radar.auth.service import set_admin
    from radar.db import session_scope

    async with register(api, "reader") as reader, register(api, "admin") as admin:
        async with session_scope() as session:
            email = (await admin.get("/auth/me")).json()["email"]
            assert await set_admin(session, email, is_admin=True)
        async with client(api) as guest:
            assert (await guest.post("/auth/demo")).json()["is_admin"] is False
            guest_refresh = await guest.post("/sources/refresh")

        assert (await reader.get("/sources")).status_code == 200
        new_source = {"name": "Лента", "feed_url": "https://example.org/rss", "category": "it"}
        assert (await reader.post("/sources", json=new_source)).status_code == 403
        assert (await reader.post("/sources/refresh")).status_code == 403
        assert guest_refresh.status_code == 403
        # The role is read from the session cache, which is dropped on sign-in.
        await admin.post("/auth/logout")
        await admin.post("/auth/login", json={"email": email, "password": PASSWORD})
        assert (await admin.post("/sources/refresh")).status_code == 202


@pytest.mark.parametrize(
    ("auth", "guest_status"),
    [("on", 404), ("off", 200)],
    ids=["sign-in required", "no sign-in"],
)
async def test_without_sign_in_every_visitor_may_enter_as_a_guest(
    api: str, monkeypatch: pytest.MonkeyPatch, auth: str, guest_status: int
) -> None:
    from radar.config import get_settings

    # The guest button is off; with sign-in off a visitor still gets in.
    monkeypatch.setenv("RADAR_AUTH", auth)
    monkeypatch.setenv("RADAR_DEMO_LOGIN", "false")
    get_settings.cache_clear()
    try:
        async with client(api) as visitor:
            meta = (await visitor.get("/meta")).json()
            entered = await visitor.post("/auth/demo")
    finally:
        get_settings.cache_clear()

    assert meta["sign_in_required"] is (auth == "on")
    assert entered.status_code == guest_status


async def test_every_guest_gets_an_own_copy_of_the_examples(api: str) -> None:
    async with client(api) as first, client(api) as second:
        await first.post("/auth/demo")
        await second.post("/auth/demo")
        mine = (await first.get("/profiles")).json()
        theirs = (await second.get("/profiles")).json()
        await first.delete(f"/profiles/{mine[0]['id']}")

        assert [item["spec"]["name"] for item in mine] == [item["spec"]["name"] for item in theirs]
        assert {item["id"] for item in mine}.isdisjoint(item["id"] for item in theirs)
        # A change made by one visitor is invisible to another.
        assert len((await second.get("/profiles")).json()) == len(theirs)
        assert (await second.get(f"/profiles/{mine[1]['id']}")).status_code == 404


async def test_a_request_from_another_site_is_refused_even_with_a_valid_cookie(api: str) -> None:
    async with register(api, "carol") as reader:
        forged = await reader.post(
            "/profiles", json=profile_spec(), headers={"Sec-Fetch-Site": "cross-site"}
        )
        own = await reader.post(
            "/profiles", json=profile_spec(), headers={"Sec-Fetch-Site": "same-origin"}
        )

    assert forged.status_code == 403
    assert own.status_code == 201


async def test_resume_is_analysed_and_the_file_is_not_kept(api: str) -> None:
    from radar.db import session_scope
    from radar.db.models import Resume
    from radar.resume import service
    from tests.test_resume import ICS_RESUME

    async with register(api, "ivan") as reader:
        user_id = uuid.UUID((await reader.get("/auth/me")).json()["id"])
        assert (await reader.get("/resume")).json() is None

        accepted = await reader.post(
            "/resume", content=ICS_RESUME.encode(), headers={"X-File-Name": "cv.txt"}
        )
        assert accepted.status_code == 202
        assert accepted.json()["status"] == "processing"
        async with session_scope() as session:
            stored = await session.scalar(
                select(Resume).where(Resume.user_id == user_id).options(undefer(Resume.payload))
            )
            assert stored is not None
            assert stored.payload is not None
            uploaded_at = stored.created_at

        # What the worker does when it takes the task.
        assert await service.process(user_id, uploaded_at) is True

        ready = (await reader.get("/resume")).json()
        assert ready["status"] == "ready"
        assert ready["parser"] == "builtin"
        assert ready["facts"]["headline"] == "Ведущий инженер по защите АСУ ТП"
        assert ready["suggestion"]["interests"][0]["id"] == "ics-security"
        async with session_scope() as session:
            row = await session.scalar(
                select(Resume).where(Resume.user_id == user_id).options(undefer(Resume.payload))
            )
            assert row is not None
            assert row.payload is None
            # Nothing from the contact block survived anywhere in the row.
            kept = f"{row.facts} {row.suggestion}"
            assert "Петров" not in kept
            assert "example.org" not in kept
        # The suggestion is a valid profile as it stands.
        assert (await reader.post("/profiles", json=ready["suggestion"])).status_code == 201

        assert (await reader.delete("/resume")).status_code == 204
        assert (await reader.get("/resume")).json() is None


async def test_resume_upload_limits(api: str) -> None:
    from radar.config import get_settings

    limit = get_settings().resume_max_bytes
    async with register(api, "dina") as reader:
        too_large = await reader.post("/resume", content=b"%PDF-" + b"0" * limit)
        not_a_document = await reader.post("/resume", content=b"MZ\x90\x00" + b"\x00" * 200)
        needs_docling = await reader.post("/resume", content=b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)

    assert too_large.status_code == 413
    assert not_a_document.status_code == 415
    assert needs_docling.status_code == 415


async def test_feed_follows_the_profile_and_the_readers_reactions(api: str) -> None:
    from radar.db import session_scope
    from radar.db.models import Interaction

    ids = await seed_articles()
    async with register(api, "egor") as reader:
        cold = (await reader.get("/feed")).json()
        assert {item["article_id"] for item in cold["items"]} == set(ids.values())
        assert all(item["explore"] for item in cold["items"])

        await reader.post("/profiles", json=profile_spec())
        feed = (await reader.get("/feed")).json()["items"]
        on_topic = [item["article_id"] for item in feed if not item["explore"]]
        assert set(on_topic) == {ids["vpn"], ids["router"], ids["router2"]}
        assert feed[0]["reasons"][0] == {"kind": "interest", "text": "Интерес «Сети»"}

        # A dislike removes the article from the feed; taking it back returns it.
        verdict = {"article_id": ids["vpn"], "kind": "dislike"}
        assert (await reader.post("/feedback", json=verdict)).status_code == 204
        after = [item["article_id"] for item in (await reader.get("/feed")).json()["items"]]
        assert ids["vpn"] not in after
        await reader.post("/feedback", json={**verdict, "active": False})
        restored = [item["article_id"] for item in (await reader.get("/feed")).json()["items"]]
        assert ids["vpn"] in restored

        # A like replaces a dislike instead of sitting next to it.
        await reader.post("/feedback", json=verdict)
        await reader.post("/feedback", json={"article_id": ids["vpn"], "kind": "like"})
        await reader.post("/feedback", json={"article_id": ids["soup"], "kind": "save"})
        reactions = (
            await reader.get("/reactions", params={"article_id": [ids["vpn"], ids["soup"]]})
        ).json()
        assert reactions == {str(ids["vpn"]): ["like"], str(ids["soup"]): ["save"]}
        saved = (await reader.get("/feed/saved")).json()
        assert [item["article_id"] for item in saved["items"]] == [ids["soup"]]

        # The reactions became a learned facet, named after the strongest one
        # (a save outweighs a like). How it moves the ranking is covered by
        # test_recsys.py on controlled vectors.
        taste = (await reader.get("/taste")).json()
        assert {facet["kind"] for facet in taste["facets"]} == {"interest", "learned"}
        learned = [facet["label"] for facet in taste["facets"] if facet["kind"] == "learned"]
        assert learned == ["Рецепт борща: свёкла, капуста и говяжий бульон"]
        assert taste["positives"] == 2
        assert (
            await reader.post("/feedback", json={"article_id": 10**9, "kind": "like"})
        ).status_code == 404

        password = {"password": PASSWORD}
        user_id = (await reader.get("/auth/me")).json()["id"]
        assert (await reader.post("/auth/me/delete", json={"password": "wrong"})).status_code == 403
        assert (await reader.post("/auth/me/delete", json=password)).status_code == 204
        assert (await reader.get("/auth/me")).json() is None
    async with session_scope() as session:
        left = await session.scalar(
            select(func.count())
            .select_from(Interaction)
            .where(Interaction.user_id == uuid.UUID(user_id))
        )
    assert left == 0


async def test_a_hidden_article_stays_hidden_however_many_signals_follow(
    api: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from radar.recsys import store

    ids = await seed_articles()
    # Only the newest signal of each kind feeds the learned taste here.
    monkeypatch.setattr(store, "SIGNAL_LIMIT", 1)
    monkeypatch.setattr(store, "OPEN_LIMIT", 1)
    async with register(api, "fedor") as reader:
        await reader.post("/profiles", json=profile_spec())
        await reader.post("/feedback", json={"article_id": ids["vpn"], "kind": "hide"})
        for key in ("router", "router2", "cake"):
            await reader.post("/feedback", json={"article_id": ids[key], "kind": "like"})
            await reader.post("/feedback", json={"article_id": ids[key], "kind": "open"})

        feed = [item["article_id"] for item in (await reader.get("/feed")).json()["items"]]

    assert ids["vpn"] not in feed


async def test_pages_come_from_one_ranking_even_after_a_reaction(api: str) -> None:
    ids = await seed_articles()
    async with register(api, "galina") as reader:
        await reader.post("/profiles", json=profile_spec())
        first = (await reader.get("/feed", params={"limit": 2})).json()
        # A reaction between two pages changes the taste and would re-rank.
        await reader.post("/feedback", json={"article_id": ids["soup"], "kind": "save"})
        rest = (
            await reader.get(
                "/feed", params={"limit": 50, "offset": 2, "snapshot": first["snapshot"]}
            )
        ).json()
        rebuilt = (await reader.get("/feed", params={"limit": 50})).json()

    paged = [item["article_id"] for item in first["items"] + rest["items"]]
    assert rest["snapshot"] == first["snapshot"]
    assert len(paged) == len(set(paged)) == first["total"]
    # Without the snapshot the reader gets a new ranking that knows the save.
    assert rebuilt["snapshot"] != first["snapshot"]


# A few bytes that pass for an MP4: the service checks the "ftyp" box only.
FAKE_MP4 = b"\x00\x00\x00\x20ftypisom" + bytes(range(200))


@pytest.fixture
def shorts_on(
    api: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[list[dict[str, Any]]]:
    """Videos switched on, with a fake renderer and no voice. Returns the props
    the renderer was called with."""
    from radar.config import get_settings
    from radar.shorts import service
    from radar.worker import tasks

    monkeypatch.setenv("RADAR_SHORTS_URL", "http://shorts.test")
    monkeypatch.setenv("RADAR_TTS_URL", "")
    monkeypatch.setenv("RADAR_MEDIA_DIR", str(tmp_path))
    get_settings.cache_clear()
    for task in (tasks.make_short, tasks.purge_short_files):
        monkeypatch.setattr(task, "kiq", AsyncMock())
    rendered: list[dict[str, Any]] = []

    async def fake_render(
        url: str,
        props: dict[str, Any],
        audio: bytes | None,
        images: list[bytes | None],
        *,
        request_timeout: float,
    ) -> bytes:
        rendered.append(props)
        return FAKE_MP4

    async def no_pictures(article_ids: list[int]) -> list[None]:
        return [None] * len(article_ids)

    monkeypatch.setattr(service, "render", fake_render)
    monkeypatch.setattr(service, "beat_pictures", no_pictures)
    yield rendered
    get_settings.cache_clear()


async def finished_digest(
    owner: httpx.AsyncClient, ids: dict[str, int], *, status: str = "done"
) -> str:
    """A digest as a finished build leaves it: two topics over seeded articles."""
    from radar.db import session_scope
    from radar.db.models import Digest, DigestItem, DigestTopic

    profile = (await owner.post("/profiles", json=profile_spec())).json()
    now = datetime.now(UTC)
    async with session_scope() as session:
        digest = Digest(
            user_id=uuid.UUID((await owner.get("/auth/me")).json()["id"]),
            profile_id=uuid.UUID(profile["id"]),
            profile_spec=profile["spec"],
            profile_version=1,
            period_start=now - timedelta(days=7),
            period_end=now,
            status=status,
            title="Выпуск",
            finished_at=now,
        )
        session.add(digest)
        await session.flush()
        layout = {"Уязвимости": ["vpn", "router"], "Настройка": ["router2"]}
        position = 0
        for topic_position, (title, keys) in enumerate(layout.items()):
            topic = DigestTopic(digest_id=digest.id, position=topic_position, title=title)
            session.add(topic)
            await session.flush()
            for rank, key in enumerate(keys):
                session.add(
                    DigestItem(
                        digest_id=digest.id,
                        topic_id=topic.id,
                        article_id=ids[key],
                        position=position,
                        selected=True,
                        score=0.9 - 0.1 * rank - 0.2 * topic_position,
                        interest_id="net",
                        summary="Уязвимость с оценкой CVSS 9.8 закрыта. Обновите прошивку.",
                    )
                )
                position += 1
    return str(digest.id)


async def test_a_short_is_made_for_the_owner_of_a_finished_digest_only(
    api: str, shorts_on: list[dict[str, Any]]
) -> None:
    from radar.db import session_scope
    from radar.db.models import Video
    from radar.shorts import service
    from radar.worker import tasks

    async with register(api, "olga") as owner, register(api, "petr") as other:
        digest_id = await finished_digest(owner, await seed_articles())

        assert (await other.post(f"/digests/{digest_id}/short")).status_code == 404
        assert (await other.get(f"/digests/{digest_id}/short")).json() is None
        ordered = await owner.post(f"/digests/{digest_id}/short")
        again = await owner.post(f"/digests/{digest_id}/short")
        assert ordered.status_code == again.status_code == 202
        assert ordered.json()["status"] == again.json()["status"] == "queued"
        # A second press while it is queued does not queue a second video.
        tasks.make_short.kiq.assert_awaited_once()  # type: ignore[attr-defined]
        video_id = uuid.UUID(tasks.make_short.kiq.await_args.args[0])  # type: ignore[attr-defined]

        assert await service.process(video_id)

        video = (await owner.get(f"/digests/{digest_id}/short")).json()
        assert video["status"] == "done"
        assert video["voice"] is None
        assert video["size_bytes"] == len(FAKE_MP4)
        played = await owner.get(video["url"].removeprefix("/api/v1"))
        seek = await owner.get(video["url"].removeprefix("/api/v1"), headers={"Range": "bytes=0-7"})
        stolen = await other.get(f"/digests/{digest_id}/short.mp4")

        assert played.status_code == 200
        assert played.headers["content-type"] == "video/mp4"
        assert played.content == FAKE_MP4
        assert seek.status_code == 206
        assert seek.content == FAKE_MP4[:8]
        assert stolen.status_code == 404

        # The strongest item of each topic first, then the runner-up.
        props = shorts_on[0]
        assert [beat["fact"] for beat in props["beats"]] == ["CVSS 9.8"] * 3
        assert props["audience"] == "Сети"
        assert props["words"]
        assert props["hookEndMs"] <= props["beats"][0]["startMs"]
        assert props["outroStartMs"] >= props["beats"][-1]["endMs"]

        assert (await owner.delete(f"/digests/{digest_id}")).status_code == 204
        async with session_scope() as session:
            assert await session.get(Video, video_id) is None
        assert service.video_path(video_id).is_file()
        assert await service.purge_files() == 1
        assert not service.video_path(video_id).exists()


async def test_a_short_needs_a_renderer_and_a_finished_digest(
    api: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from radar.config import get_settings

    async with register(api, "roman") as reader:
        building = await finished_digest(reader, await seed_articles(), status="running")
        without_renderer = await reader.post(f"/digests/{building}/short")
        monkeypatch.setenv("RADAR_SHORTS_URL", "http://shorts.test")
        get_settings.cache_clear()
        try:
            not_ready = await reader.post(f"/digests/{building}/short")
        finally:
            monkeypatch.delenv("RADAR_SHORTS_URL")
            get_settings.cache_clear()

    assert without_renderer.status_code == 503
    assert not_ready.status_code == 409


async def test_a_reader_makes_one_video_at_a_time_and_a_new_cut_replaces_the_old(
    api: str, shorts_on: list[dict[str, Any]]
) -> None:
    from radar.shorts import service
    from radar.worker import tasks

    async with register(api, "sergei") as reader:
        ids = await seed_articles()
        first = await finished_digest(reader, ids)
        second = await finished_digest(reader, ids)

        ordered = await reader.post(f"/digests/{first}/short")
        other_digest = await reader.post(f"/digests/{second}/short")
        assert ordered.status_code == 202
        # Enforced by a unique index, so racing requests are refused too.
        assert other_digest.status_code == 429

        old_id = uuid.UUID(tasks.make_short.kiq.await_args.args[0])  # type: ignore[attr-defined]
        assert await service.process(old_id)
        again = await reader.post(f"/digests/{first}/short")
        new_id = uuid.UUID(tasks.make_short.kiq.await_args.args[0])  # type: ignore[attr-defined]

        assert again.status_code == 202
        assert new_id != old_id
        # A task left over from the first cut finds nothing to do.
        assert not await service.process(old_id)
        assert await service.process(new_id)
        assert await service.purge_files() == 1
        assert not service.video_path(old_id).exists()
        assert service.video_path(new_id).is_file()


async def test_a_reader_picks_a_voice_from_the_ones_the_service_offers(
    api: str, shorts_on: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    from radar.cache import get_cache
    from radar.config import get_settings
    from radar.shorts.service import VOICES_KEY

    monkeypatch.setenv("RADAR_TTS_URL", "http://tts.test")
    get_settings.cache_clear()
    offered = [
        {"id": "anchor", "title": "Ведущий", "default": True},
        {"id": "blogger", "title": "Блогер", "default": False},
    ]
    await get_cache().set_json(VOICES_KEY, offered, 60)

    async with register(api, "tamara") as reader, register(api, "stranger") as stranger:
        digest_id = await finished_digest(reader, await seed_articles())
        meta = (await reader.get("/meta")).json()
        unknown = await reader.post(f"/digests/{digest_id}/short", json={"voice": "robot"})
        foreign = await stranger.post(f"/digests/{digest_id}/short", json={"voice": "robot"})
        picked = await reader.post(f"/digests/{digest_id}/short", json={"voice": "blogger"})

    assert [voice["id"] for voice in meta["short_voices"]] == ["anchor", "blogger"]
    assert unknown.status_code == 400
    # Someone else's digest is missing, whatever voice is asked for.
    assert foreign.status_code == 404
    assert picked.status_code == 202
    assert picked.json()["requested_voice"] == "blogger"


async def test_a_voice_is_taken_on_trust_before_the_worker_lists_them(
    api: str, shorts_on: list[dict[str, Any]]
) -> None:
    from radar.cache import get_cache
    from radar.shorts.service import VOICES_KEY

    await get_cache().delete(VOICES_KEY)

    async with register(api, "ulyana") as reader:
        digest_id = await finished_digest(reader, await seed_articles())
        picked = await reader.post(f"/digests/{digest_id}/short", json={"voice": "anchor-2"})

    assert picked.status_code == 202
    assert picked.json()["requested_voice"] == "anchor-2"
