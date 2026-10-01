# ruff: noqa: F811  (the fixtures are imported from the accounts tests)
"""Publishing end to end on the database, with the mock Bot API in-process:
a reader connects a bot and channels, posts are planned, written and sent."""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from tests.test_accounts_api import (  # noqa: F401  (fixtures)
    api,
    database,
    profile_spec,
    register,
    seed_articles,
)

TOKEN = "987654321:AAF" + "q" * 32


@pytest.fixture
async def telegram(api: str, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[ModuleType]:
    """Every Telegram call goes to the mock app; tasks are run by the test."""
    from radar.config import get_settings
    from radar.publishing import compose, mock_api
    from radar.publishing import telegram as telegram_module
    from radar.worker import tasks

    monkeypatch.setenv("RADAR_SECRET_KEY", "test-secret-key-0123456789")
    monkeypatch.setenv("RADAR_TELEGRAM_API_URL", "http://telegram.mock")
    get_settings.cache_clear()
    compose.get_post_writer.cache_clear()
    monkeypatch.setattr(telegram_module, "DEFAULT_TRANSPORT", httpx.ASGITransport(app=mock_api.app))
    for task in (tasks.compose_post, tasks.send_post):
        monkeypatch.setattr(task, "kiq", AsyncMock())
    mock_api._messages.clear()
    mock_api._calls.clear()
    mock_api._chats.clear()
    yield mock_api
    get_settings.cache_clear()


async def connect(
    reader: httpx.AsyncClient, chat: str, *, media: str = "none", **settings: Any
) -> dict[str, Any]:
    """A bot (once), a channel for the reader's first profile, and its settings."""
    bots = (await reader.get("/publishing/bots")).json()
    bot = bots[0] if bots else (await reader.post("/publishing/bots", json={"token": TOKEN})).json()
    profiles = (await reader.get("/profiles")).json()
    profile = (
        profiles[0] if profiles else (await reader.post("/profiles", json=profile_spec())).json()
    )
    response = await reader.post(
        "/publishing/channels",
        json={"bot_id": bot["id"], "chat": chat, "profile_id": profile["id"]},
    )
    assert response.status_code == 201, response.text
    channel = response.json()
    merged = {**channel["settings"], **settings}
    merged["format"] = {**merged["format"], "media": media}
    updated = await reader.patch(f"/publishing/channels/{channel['id']}", json={"settings": merged})
    assert updated.status_code == 200, updated.text
    return updated.json()


async def write_and_send(post_id: str, *, now: datetime | None = None) -> str:
    from radar.cache import get_cache
    from radar.publishing import service

    assert await service.compose(uuid.UUID(post_id), get_cache()) == service.QUEUED
    assert uuid.UUID(post_id) in await service.due(now)
    return await service.send(uuid.UUID(post_id), now=now)


async def test_a_reader_connects_a_bot_and_a_channel_and_a_post_goes_out(
    api: str, telegram: ModuleType
) -> None:
    async with register(api, "olga") as reader:
        bot = await reader.post("/publishing/bots", json={"token": TOKEN})
        no_rights = await reader.post(
            "/publishing/channels", json={"bot_id": bot.json()["id"], "chat": "@no_rights_channel"}
        )
        ids = await seed_articles()
        channel = await connect(reader, "https://t.me/radar_demo")
        post = (
            await reader.post(f"/publishing/channels/{channel['id']}/posts", json={"publish": True})
        ).json()

        assert await write_and_send(post["id"]) == "sent"
        [sent] = (
            await reader.get("/publishing/posts", params={"channel_id": channel["id"]})
        ).json()

    assert bot.status_code == 201
    # The token is checked, stored and never shown again.
    assert TOKEN not in bot.text
    assert bot.json()["token_hint"] == "987654321:…qqqq"
    assert no_rights.status_code == 400
    assert (channel["title"], channel["username"]) == ("Radar Demo", "radar_demo")
    assert sent["status"] == "sent"
    assert sent["message_url"] == "https://t.me/radar_demo/1"
    # The story is one of the network ones, not the soup.
    assert sent["articles"][0]["id"] in {ids["vpn"], ids["router"], ids["router2"]}
    [message] = telegram._messages
    assert message["method"] == "sendMessage"
    assert message["payload"]["parse_mode"] == "HTML"
    assert "<b>" in message["payload"]["text"]
    assert ">здесь</a>." in message["payload"]["text"]


class RecordingWriter:
    """The offline writer, remembering what each channel was told."""

    name = "recording"

    def __init__(self) -> None:
        from radar.publishing.writer import HeuristicPostWriter

        self.inner = HeuristicPostWriter()
        self.others: list[tuple[str, ...]] = []

    async def news(self, story: Any, voice: Any) -> Any:
        self.others.append(voice.others)
        return await self.inner.news(story, voice)

    async def digest(self, stories: Any, voice: Any) -> Any:
        return await self.inner.digest(stories, voice)


async def test_a_second_channel_writes_the_same_story_knowing_how_the_first_told_it(
    api: str, telegram: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    from radar.publishing import compose

    writer = RecordingWriter()
    monkeypatch.setattr(compose, "get_post_writer", lambda: writer)
    async with register(api, "pavel") as reader:
        ids = await seed_articles()
        first = await connect(reader, "@radar_it")
        second = await connect(
            reader,
            "@radar_ot",
            links={"mode": "button", "inline_text": "здесь", "button_text": "Читать", "utm": ""},
        )
        for channel in (first, second):
            post = (
                await reader.post(
                    f"/publishing/channels/{channel['id']}/posts",
                    json={"article_id": ids["vpn"], "publish": True},
                )
            ).json()
            assert await write_and_send(post["id"]) == "sent"

    assert writer.others[0] == ()
    assert "Уязвимость в VPN-шлюзах" in writer.others[1][0]
    by_chat = {message["chat"]["username"]: message["payload"] for message in telegram._messages}
    # Same story, the link where each channel wants it: a word, or a button.
    assert "href=" in by_chat["radar_it"]["text"]
    assert "reply_markup" not in by_chat["radar_it"]
    assert by_chat["radar_ot"]["reply_markup"]["inline_keyboard"][0][0]["text"] == "Читать"


async def test_a_rate_limited_post_waits_and_a_blocked_picture_is_uploaded(
    api: str, telegram: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy import update

    from radar.cache import get_cache
    from radar.db import session_scope
    from radar.db.models import Article
    from radar.images.service import Picture
    from radar.publishing import service

    monkeypatch.setattr(
        service, "mirror", AsyncMock(return_value=Picture(b"\xff\xd8\xffpicture", "jpg"))
    )
    async with register(api, "rita") as reader:
        ids = await seed_articles()
        async with session_scope() as session:
            await session.execute(
                update(Article)
                .where(Article.id == ids["router"])
                .values(image_url="https://cdn.example.org/hotlink/router.jpg")
            )
        channel = await connect(reader, "@flaky_channel", media="auto")
        post = (
            await reader.post(
                f"/publishing/channels/{channel['id']}/posts",
                json={"article_id": ids["router"], "publish": True},
            )
        ).json()
        post_id = uuid.UUID(post["id"])
        now = datetime.now(UTC)

        assert await service.compose(post_id, get_cache()) == service.QUEUED
        assert post_id in await service.due(now)
        first = await service.send(post_id, now=now)
        too_early = await service.due(now + timedelta(seconds=1))
        later = now + timedelta(seconds=10)
        assert post_id in await service.due(later)
        second = await service.send(post_id, now=later)

    assert first == "queued"
    assert post_id not in too_early
    assert second == "sent"
    [message] = telegram._messages
    assert message["method"] == "sendPhoto"
    assert message["payload"]["photo"].startswith("uploaded:")


async def test_another_reader_sees_and_touches_nothing(api: str, telegram: ModuleType) -> None:
    async with register(api, "sergey") as owner, register(api, "stranger") as stranger:
        await seed_articles()
        channel = await connect(owner, "@radar_sec")
        post = (await owner.post(f"/publishing/channels/{channel['id']}/posts", json={})).json()

        seen = (await stranger.get("/publishing/channels")).json()
        posts = (await stranger.get("/publishing/posts")).json()
        patched = await stranger.patch(
            f"/publishing/channels/{channel['id']}", json={"enabled": False}
        )
        published = await stranger.post(f"/publishing/posts/{post['id']}/publish")
        bots = (await stranger.get("/publishing/bots")).json()

    assert seen == []
    assert posts == []
    assert bots == []
    assert patched.status_code == 404
    assert published.status_code == 404


async def test_slots_are_planned_once_and_a_draft_waits_for_approval(
    api: str, telegram: ModuleType
) -> None:
    from radar.cache import get_cache
    from radar.publishing import service

    async with register(api, "tanya") as reader:
        await seed_articles()
        channel = await connect(
            reader,
            "@radar_drafts",
            approval="manual",
            schedule={
                "mode": "interval",
                "every_minutes": 60,
                "window_start": "00:00",
                "window_end": "23:59",
                "prepare_minutes": 90,
                "max_per_day": 24,
            },
        )
        now = datetime.now(UTC)
        planned = await service.plan(now)
        again = await service.plan(now)
        mine = [post_id for post_id in planned if post_id in set(planned)]
        status = await service.compose(mine[0], get_cache())
        [draft] = [
            post
            for post in (
                await reader.get("/publishing/posts", params={"channel_id": channel["id"]})
            ).json()
            if post["status"] == "draft"
        ]
        edited = await reader.patch(
            f"/publishing/posts/{draft['id']}",
            json={
                "content": {
                    **draft["content"],
                    "html": "<p>Свой <b>текст</b><script>x()</script></p>",
                },
                "approve": True,
            },
        )

    assert planned
    assert again == []
    assert status == "draft"
    assert edited.status_code == 200, edited.text
    assert edited.json()["status"] == "queued"
    assert edited.json()["content"]["html"] == "<p>Свой <b>текст</b></p>"


HOURLY = {
    "mode": "interval",
    "every_minutes": 60,
    "window_start": "00:00",
    "window_end": "23:59",
    "prepare_minutes": 90,
    "max_per_day": 24,
}


async def test_a_post_removed_while_it_is_written_stays_removed(
    api: str, telegram: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    from radar.cache import get_cache
    from radar.publishing import compose, service

    async with register(api, "ulyana") as reader:
        await seed_articles()
        channel = await connect(reader, "@radar_cancel", schedule=HOURLY)
        [post_id, *_] = await service.plan(datetime.now(UTC))

        class CancellingWriter(RecordingWriter):
            """The owner removes the post while the model is still writing it."""

            async def news(self, story: Any, voice: Any) -> Any:
                assert (await reader.delete(f"/publishing/posts/{post_id}")).status_code == 204
                return await super().news(story, voice)

        monkeypatch.setattr(compose, "get_post_writer", CancellingWriter)
        status = await service.compose(post_id, get_cache())
        sent = await service.due(datetime.now(UTC) + timedelta(hours=3))
        posts = (await reader.get("/publishing/posts", params={"channel_id": channel["id"]})).json()

    assert status == "gone"
    assert post_id not in sent
    assert {post["status"] for post in posts if post["id"] == str(post_id)} == {"skipped"}
    assert telegram._messages == []


class Unreachable(httpx.AsyncBaseTransport):
    """Telegram as the network sees it when something breaks on the way."""

    def __init__(self, error: type[httpx.TransportError]) -> None:
        self.error = error

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        raise self.error("simulated", request=request)


async def test_a_post_that_may_have_reached_telegram_is_not_sent_again(
    api: str, telegram: ModuleType
) -> None:
    from radar.cache import get_cache
    from radar.publishing import service

    async with register(api, "vera") as reader:
        ids = await seed_articles()
        channel = await connect(reader, "@radar_timeouts")
        sent: dict[str, str] = {}
        for error, article in ((httpx.ReadTimeout, "vpn"), (httpx.ConnectError, "router")):
            post = (
                await reader.post(
                    f"/publishing/channels/{channel['id']}/posts",
                    json={"article_id": ids[article], "publish": True},
                )
            ).json()
            post_id = uuid.UUID(post["id"])
            assert await service.compose(post_id, get_cache()) == service.QUEUED
            assert post_id in await service.due()
            sent[error.__name__] = await service.send(post_id, transport=Unreachable(error))
        posts = (await reader.get("/publishing/posts", params={"channel_id": channel["id"]})).json()

    # The answer was lost on the way back: the post may be in the channel, so
    # the owner decides. The connection never opened: it is simply tried again.
    assert sent == {"ReadTimeout": "failed", "ConnectError": "queued"}
    lost = next(post for post in posts if post["status"] == "failed")
    assert "пост мог выйти" in lost["error"]


async def test_a_scheduled_post_that_is_late_waits_for_a_human(
    api: str, telegram: ModuleType
) -> None:
    from radar.cache import get_cache
    from radar.publishing import service

    async with register(api, "yana") as reader:
        await seed_articles()
        channel = await connect(reader, "@radar_late", schedule=HOURLY)
        now = datetime.now(UTC)
        [post_id, *_] = await service.plan(now)
        assert await service.compose(post_id, get_cache()) == service.QUEUED
        late = await service.due(now + timedelta(hours=3))
        [post] = [
            post
            for post in (
                await reader.get("/publishing/posts", params={"channel_id": channel["id"]})
            ).json()
            if post["id"] == str(post_id)
        ]
        approved = await reader.patch(f"/publishing/posts/{post_id}", json={"approve": True})
        then = await service.due(now + timedelta(hours=3, minutes=1))

    assert post_id not in late
    assert (post["status"], post["error"]) == ("draft", service.LATE_NOTE)
    # Once a human says yes, it goes out however late it is.
    assert approved.json()["status"] == "queued"
    assert post_id in then
