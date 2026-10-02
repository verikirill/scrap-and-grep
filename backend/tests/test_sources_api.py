# ruff: noqa: F811  (the fixtures are imported from the other tests)
"""A Telegram channel as a source: added by an administrator, read into articles.

Needs PostgreSQL and Valkey; skipped without them.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import func, select

from tests.test_accounts_api import PASSWORD, api, database, register  # noqa: F401
from tests.test_telegram import channel_page, offline  # noqa: F401

pytestmark = pytest.mark.integration


@asynccontextmanager
async def administrator(base_url: str) -> AsyncIterator[httpx.AsyncClient]:
    from radar.auth.service import set_admin
    from radar.db import session_scope

    async with register(base_url, "admin") as admin:
        email = (await admin.get("/auth/me")).json()["email"]
        async with session_scope() as session:
            assert await set_admin(session, email, is_admin=True)
        # The role is read from the session cache, which is dropped on sign-in.
        await admin.post("/auth/logout")
        await admin.post("/auth/login", json={"email": email, "password": PASSWORD})
        yield admin


async def test_an_administrator_adds_a_channel_by_its_address(
    api: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from radar.ingest import telegram
    from radar.worker import tasks

    async def title(_: httpx.AsyncClient, name: str) -> str:
        if name == "closed_one":
            raise telegram.ChannelUnavailable(name)
        return "Радар ИБ"

    monkeypatch.setattr(telegram, "channel_title", title)
    monkeypatch.setattr(tasks.ingest_source_task, "kiq", AsyncMock())
    channel = {"kind": "telegram", "category": "security", "fetch_full_text": True}

    async with administrator(api) as admin:
        added = await admin.post("/sources", json={**channel, "channel": "https://t.me/s/Radar_IB"})
        again = await admin.post("/sources", json={**channel, "channel": "@radar_ib"})
        closed = await admin.post("/sources", json={**channel, "channel": "@closed_one"})
        elsewhere = await admin.post("/sources", json={**channel, "channel": "example.org/radar"})

    assert added.status_code == 201, added.text
    source = added.json()
    assert source["kind"] == "telegram"
    # The channel's own title, as no name was given.
    assert source["name"] == "Радар ИБ"
    assert source["feed_url"] == "https://t.me/s/radar_ib"
    assert source["site_url"] == "https://t.me/radar_ib"
    tasks.ingest_source_task.kiq.assert_awaited_once_with(source["id"])
    # Names differ only in case in Telegram.
    assert again.status_code == 409
    assert closed.status_code == 422
    assert "веб-превью" in closed.json()["detail"]
    assert elsewhere.status_code == 422
    assert "t.me" in elsewhere.json()["detail"]


async def test_a_channel_is_read_into_articles_and_then_from_where_it_stopped(
    api: str, offline: None
) -> None:
    from radar.cache import get_cache
    from radar.db import session_scope
    from radar.db.models import Article, Source
    from radar.ingest.service import ingest_source

    async with session_scope() as session:
        source = Source(
            slug="tg-radar_ib",
            name="Радар ИБ",
            kind="telegram",
            feed_url="https://t.me/s/radar_ib",
            site_url="https://t.me/radar_ib",
            category="security",
        )
        session.add(source)
        await session.flush()
        source_id = source.id

    newest = 3

    def handle(request: httpx.Request) -> httpx.Response:
        before = request.url.params.get("before")
        ids = range(1, newest + 1) if before is None else range(1, int(before))
        return httpx.Response(200, text=channel_page(ids))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        first = await ingest_source(source_id, client, get_cache())
        newest = 5
        second = await ingest_source(source_id, client, get_cache())
        unchanged = await ingest_source(source_id, client, get_cache())

    async with session_scope() as session:
        stored = await session.scalar(
            select(func.count()).select_from(Article).where(Article.source_id == source_id)
        )
        source = await session.get(Source, source_id)
    assert (first.status, first.new_articles) == ("ok", 3)
    assert (second.status, second.new_articles) == ("ok", 2)
    assert unchanged.status == "not_modified"
    assert stored == 5
    assert source is not None
    assert source.last_post_id == 5
    assert source.consecutive_failures == 0


async def test_the_trending_page_of_pt_comes_with_the_defaults_and_is_read(
    api: str, offline: None
) -> None:
    from radar.cache import get_cache
    from radar.db import session_scope
    from radar.db.models import Article, Source
    from radar.ingest.service import ingest_source
    from tests.test_official_sources import PT_PAGE

    async with session_scope() as session:
        trending = await session.scalar(select(Source).where(Source.slug == "pt-trending"))
        incident = await session.scalar(select(Source).where(Source.slug == "bdu-incident"))
    assert trending is not None
    assert incident is not None
    assert (trending.kind, incident.kind, incident.fetch_full_text) == ("pt_trending", "rss", True)

    page = httpx.MockTransport(lambda _: httpx.Response(200, text=PT_PAGE))
    async with httpx.AsyncClient(transport=page) as client:
        report = await ingest_source(trending.id, client, get_cache())

    async with session_scope() as session:
        titles = list(
            await session.scalars(select(Article.title).where(Article.source_id == trending.id))
        )
    assert (report.status, report.new_articles) == ("ok", 3)
    assert "Трендовая уязвимость CVE-2026-99002 в Microsoft Windows" in titles


async def test_a_feed_that_refuses_the_bot_remembers_how_it_was_read(
    api: str, offline: None
) -> None:
    from radar.cache import get_cache
    from radar.db import session_scope
    from radar.db.models import Source
    from radar.ingest.service import ingest_source

    async with session_scope() as session:
        source = Source(
            slug="waf-feed",
            name="Сайт за WAF",
            feed_url="https://waf.example/feed",
            category="security",
        )
        session.add(source)
        await session.flush()
        source_id = source.id
    feed = (
        '<?xml version="1.0"?><rss version="2.0"><channel><title>WAF</title>'
        "<item><title>Новость</title><link>https://waf.example/news/1</link>"
        "<pubDate>Wed, 30 Sep 2026 10:00:00 GMT</pubDate></item></channel></rss>"
    )
    agents: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        agents.append(request.headers["user-agent"])
        if "Chrome/" not in request.headers["user-agent"]:
            return httpx.Response(403, text="Forbidden")
        return httpx.Response(200, text=feed)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        first = await ingest_source(source_id, client, get_cache())
        second = await ingest_source(source_id, client, get_cache())

    async with session_scope() as session:
        source = await session.get(Source, source_id)
    assert (first.status, first.new_articles) == ("ok", 1)
    assert second.status == "ok"
    assert source is not None
    assert source.fetch_method == "browser_headers"
    assert source.fetch_note == "403 на шаге «обычный запрос», прочитан через заголовки браузера"
    # The next run starts on the step that worked.
    assert ["Chrome/" in agent for agent in agents] == [False, True, True]


async def test_a_source_gets_its_own_proxy_and_its_password_is_not_shown(
    api: str, monkeypatch: pytest.MonkeyPatch, offline: None
) -> None:
    from radar.db import session_scope
    from radar.db.models import Source
    from radar.worker import tasks

    monkeypatch.setattr(tasks.ingest_source_task, "kiq", AsyncMock())
    feed = {
        "kind": "rss",
        "name": "Сайт с гео-блокировкой",
        "feed_url": "https://geo.example.com/feed",
        "category": "security",
        "proxy_url": "socks5://reader:secret@proxy.example.net:1080",
    }
    async with administrator(api) as admin:
        added = await admin.post("/sources", json=feed)
        wrong = await admin.post(
            "/sources",
            json={**feed, "feed_url": "https://b.example.com/feed", "proxy_url": "ftp://x"},
        )
        source_id = added.json()["id"]
        listed = (await admin.get("/sources")).json()
        cleared = await admin.patch(f"/sources/{source_id}", json={"proxy_url": ""})

    assert added.status_code == 201, added.text
    assert added.json()["proxy"] == "socks5://proxy.example.net:1080"
    assert "secret" not in str(listed)
    assert wrong.status_code == 422
    assert cleared.json()["proxy"] is None
    async with session_scope() as session:
        source = await session.get(Source, source_id)
    assert source is not None
    assert source.proxy_url is None
