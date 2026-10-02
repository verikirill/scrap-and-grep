# ruff: noqa: F811  (the fixtures are imported from the other tests)
"""Opening an article in the app: its page is read once, its pictures come
through the API.

Needs PostgreSQL; skipped without it.
"""

from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from tests.test_accounts_api import api, database, register  # noqa: F401
from tests.test_reader import PAGE
from tests.test_telegram import offline  # noqa: F401

pytestmark = pytest.mark.integration

PNG = b"\x89PNG\r\n\x1a\n" + bytes(64)
STORY = "https://news.example/story"


@pytest.fixture
def site(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, offline: None) -> dict[str, object]:
    """The news site behind a mock transport, and a picture store on disk.

    `site["page"]` is the story's response; requests are counted by path.
    """
    from radar.api.routes import reader as reader_routes
    from radar.images.store import LocalImageStore
    from radar.reader import service

    state: dict[str, object] = {"page": httpx.Response(200, html=PAGE), "hits": Counter()}

    def handle(request: httpx.Request) -> httpx.Response:
        hits = state["hits"]
        assert isinstance(hits, Counter)
        hits[request.url.path] += 1
        if request.url.path == "/story":
            page = state["page"]
            assert isinstance(page, httpx.Response)
            return page
        if request.url.path in {"/pics/scheme.png", "/pics/lead.jpg"}:
            return httpx.Response(200, content=PNG, headers={"Content-Type": "image/png"})
        return httpx.Response(404)

    client: Callable[[], httpx.AsyncClient] = lambda: httpx.AsyncClient(  # noqa: E731
        transport=httpx.MockTransport(handle)
    )
    monkeypatch.setattr(service, "build_client", client)
    state["client"] = client
    store = LocalImageStore(tmp_path)
    monkeypatch.setattr(reader_routes, "get_image_store", lambda: store)
    return state


async def article(url: str, *, content: str | None = None) -> int:
    from radar.db import session_scope
    from radar.db.models import Source
    from radar.store.articles import NewArticle, insert_new
    from radar.text import content_hash

    async with session_scope() as session:
        source = Source(
            slug=f"reader-{content_hash(url, '')[:8]}",
            name="Новости ИБ",
            feed_url=f"{url}/feed",
            category="security",
        )
        session.add(source)
        await session.flush()
        [article_id] = await insert_new(
            session,
            source.id,
            [
                NewArticle(
                    url=url,
                    title="Атака на подстанцию: как это было",
                    summary="Злоумышленники проникли в сеть подстанции через шлюз подрядчика.",
                    content=content,
                    author=None,
                    tags=(),
                    language="ru",
                    published_at=datetime.now(UTC),
                    content_hash=content_hash(url, "x"),
                    image_url="https://news.example/pics/lead.jpg",
                )
            ],
        )
    return article_id


async def test_an_article_is_read_from_its_page_once_and_its_pictures_through_the_api(
    api: str, site: dict[str, object]
) -> None:
    article_id = await article(STORY)

    async with register(api) as reader:
        first = await reader.get(f"/articles/{article_id}")
        again = await reader.get(f"/articles/{article_id}")
        [picture] = [block for block in first.json()["blocks"] if block["type"] == "image"]
        image = await reader.get(f"/articles/{article_id}/images/{picture['id']}")
        image_again = await reader.get(f"/articles/{article_id}/images/{picture['id']}")
        stranger = await reader.get(f"/articles/{article_id}/images/{'0' * 16}")

    assert first.status_code == 200, first.text
    read = first.json()
    assert read["complete"] is True
    assert read["title"] == "Атака на подстанцию: как это было"
    assert [block["type"] for block in read["blocks"]][:4] == ["image", "p", "p", "h"]
    # The page's words are counted for the reading time.
    assert read["reading_minutes"] == 1
    assert again.json() == read
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"
    assert image.content == PNG
    assert image_again.content == PNG
    # An address not found in the article is not fetched.
    assert stranger.status_code == 404
    assert site["hits"] == {"/story": 1, "/pics/scheme.png": 1}


async def test_a_page_that_refuses_shows_the_feed_text_and_is_tried_again_later(
    api: str, site: dict[str, object]
) -> None:
    from sqlalchemy import update

    from radar.db import session_scope
    from radar.db.models import ArticleBody

    article_id = await article(STORY)
    site["page"] = httpx.Response(403, text="Forbidden")

    async with register(api) as reader:
        refused = (await reader.get(f"/articles/{article_id}")).json()
        site["page"] = httpx.Response(200, html=PAGE)
        soon = (await reader.get(f"/articles/{article_id}")).json()
        async with session_scope() as session:
            await session.execute(
                update(ArticleBody).values(read_at=datetime.now(UTC) - timedelta(hours=7))
            )
        later = (await reader.get(f"/articles/{article_id}")).json()

    assert refused["complete"] is False
    assert [block["type"] for block in refused["blocks"]] == ["image", "p"]
    assert refused["blocks"][1]["spans"][0]["text"].startswith("Злоумышленники проникли")
    assert soon == refused
    assert later["complete"] is True
    assert "table" in {block["type"] for block in later["blocks"]}


async def test_a_telegram_post_is_shown_as_it_was_posted_without_reading_a_page(
    api: str, site: dict[str, object]
) -> None:
    post = "\n".join(
        (
            "Атака на подстанцию: как это было",
            "Злоумышленники вошли через шлюз подрядчика, разбор - https://cert.example/42.",
        )
    )
    article_id = await article("https://t.me/radar_ib/42", content=post)

    async with register(api) as reader:
        read = (await reader.get(f"/articles/{article_id}")).json()

    assert read["complete"] is True
    assert read["blocks"][1]["spans"] == [
        {"text": "Злоумышленники вошли через шлюз подрядчика, разбор - "},
        {"text": "https://cert.example/42", "href": "https://cert.example/42"},
        {"text": "."},
    ]
    assert site["hits"] == {}


async def test_a_picture_is_served_even_where_its_copy_cannot_be_kept(
    api: str, site: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    from radar.api.routes import reader as reader_routes

    class ReadOnlyStore:
        async def put(self, key: str, data: bytes) -> None:
            raise OSError(30, "Read-only file system")

        async def get(self, key: str) -> bytes | None:
            return None

    monkeypatch.setattr(reader_routes, "get_image_store", ReadOnlyStore)
    article_id = await article(STORY)

    async with register(api) as reader:
        blocks = (await reader.get(f"/articles/{article_id}")).json()["blocks"]
        [picture] = [block for block in blocks if block["type"] == "image"]
        first = await reader.get(f"/articles/{article_id}/images/{picture['id']}")
        second = await reader.get(f"/articles/{article_id}/images/{picture['id']}")

    assert (first.status_code, first.content) == (200, PNG)
    assert (second.status_code, second.content) == (200, PNG)
    # Nothing was kept, so the site is asked every time.
    assert site["hits"]["/pics/scheme.png"] == 2


async def test_a_page_read_before_keeps_its_text_when_a_new_reading_fails(
    api: str, site: dict[str, object]
) -> None:
    from sqlalchemy import select, update

    from radar.db import session_scope
    from radar.db.models import ArticleBody

    article_id = await article(STORY)
    async with register(api) as reader:
        before = (await reader.get(f"/articles/{article_id}")).json()
        # A new version of the reader wants the page again, and the site is down.
        async with session_scope() as session:
            await session.execute(update(ArticleBody).values(version=0))
        site["page"] = httpx.Response(503, text="Service Unavailable")
        after = (await reader.get(f"/articles/{article_id}")).json()
        again = (await reader.get(f"/articles/{article_id}")).json()

    async with session_scope() as session:
        status = await session.scalar(select(ArticleBody.status))
    assert after == before
    assert again == before
    assert status == "stale"
    # Tried once after the change, then left alone until RETRY_AFTER.
    assert site["hits"]["/story"] == 2


async def test_a_picture_the_site_refused_is_not_asked_for_again_at_once(
    api: str, site: dict[str, object]
) -> None:
    from radar.cache import get_cache

    if not await get_cache().ping():
        pytest.skip("Valkey is not reachable")
    article_id = await article(STORY)
    page = PAGE.replace("/pics/scheme.png", "/pics/gone.png")
    site["page"] = httpx.Response(200, html=page)

    async with register(api) as reader:
        blocks = (await reader.get(f"/articles/{article_id}")).json()["blocks"]
        [picture] = [block for block in blocks if block["type"] == "image"]
        first = await reader.get(f"/articles/{article_id}/images/{picture['id']}")
        second = await reader.get(f"/articles/{article_id}/images/{picture['id']}")

    assert (first.status_code, second.status_code) == (502, 502)
    assert site["hits"]["/pics/gone.png"] == 1
