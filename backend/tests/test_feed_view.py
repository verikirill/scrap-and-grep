# ruff: noqa: F811  (the fixtures are imported from the other tests)
"""The feed's two looks: the reader's choice, and the pictures the Telegram look shows.

Needs PostgreSQL; skipped without it.
"""

import uuid

import httpx
import pytest

from tests.test_accounts_api import (  # noqa: F401
    api,
    database,
    profile_spec,
    register,
    seed_articles,
)
from tests.test_reader import PAGE
from tests.test_reader_api import PNG, STORY, article, site  # noqa: F401
from tests.test_telegram import offline  # noqa: F401

pytestmark = pytest.mark.integration


async def test_the_look_and_the_order_of_the_feed_are_kept_with_the_account(api: str) -> None:
    async with register(api) as reader:
        before = (await reader.get("/auth/me")).json()
        view = await reader.patch("/auth/me/settings", json={"feed_view": "telegram"})
        order = await reader.patch("/auth/me/settings", json={"feed_order": "top"})
        after = (await reader.get("/auth/me")).json()
        unknown = await reader.patch("/auth/me/settings", json={"feed_order": "oldest"})

    assert (before["feed_view"], before["feed_order"]) == ("cards", "new")
    assert view.json() == {"feed_view": "telegram", "feed_order": "new"}
    # One setting changes, the other stays.
    assert order.json() == {"feed_view": "telegram", "feed_order": "top"}
    assert (after["feed_view"], after["feed_order"]) == ("telegram", "top")
    assert unknown.status_code == 422


async def test_the_new_order_shows_unseen_articles_newest_first_then_the_seen(api: str) -> None:
    ids = await seed_articles()
    async with register(api) as reader:
        await reader.post("/profiles", json=profile_spec())
        await reader.post("/feedback", json={"article_id": ids["router"], "kind": "open"})
        first = (await reader.get("/feed", params={"limit": 2, "order": "new"})).json()
        # Opening one more between two pages must not reshuffle the pages to come.
        await reader.post(
            "/feedback", json={"article_id": first["items"][0]["article_id"], "kind": "open"}
        )
        rest = (
            await reader.get(
                "/feed",
                params={"limit": 50, "offset": 2, "order": "new", "snapshot": first["snapshot"]},
            )
        ).json()

    items = first["items"] + rest["items"]
    unseen = [item for item in items if not item["seen"]]
    seen = [item for item in items if item["seen"]]
    assert len({item["article_id"] for item in items}) == len(items) == first["total"]
    assert items == unseen + seen
    assert [item["article_id"] for item in seen] == [ids["router"]]
    times = [item["published_at"] for item in unseen]
    assert times == sorted(times, reverse=True)
    # Places set by a clock, not by the ranker: it must not learn from them.
    assert {item["slot"] for item in items} == {"newest"}


async def test_an_open_feed_learns_of_a_new_relevant_article(api: str) -> None:
    from datetime import UTC, datetime

    from sqlalchemy import select

    from radar.ai.factory import get_embedder
    from radar.cache import get_cache
    from radar.db import session_scope
    from radar.db.models import Source
    from radar.ingest.service import embed_pending
    from radar.recsys.service import forget_taste
    from radar.store.articles import NewArticle, insert_new
    from radar.text import content_hash

    if not await get_cache().ping():
        pytest.skip("Valkey is not reachable")
    await seed_articles()
    async with register(api) as reader:
        await reader.post("/profiles", json=profile_spec())
        me = (await reader.get("/auth/me")).json()
        shown = (await reader.get("/feed", params={"limit": 50, "order": "new"})).json()
        before = (await reader.get("/feed/fresh", params={"since": shown["built_at"]})).json()
        # A mark ranks the list anew, but an older article moved up is no news.
        await reader.post(
            "/feedback", json={"article_id": shown["items"][-1]["article_id"], "kind": "like"}
        )
        marked = (await reader.get("/feed/fresh", params={"since": shown["built_at"]})).json()

        title = "Маршрутизатор и VPN: прошивка закрывает обход аутентификации"
        async with session_scope() as session:
            source_id = await session.scalar(select(Source.id).where(Source.slug == "test"))
            assert source_id is not None
            await insert_new(
                session,
                source_id,
                [
                    NewArticle(
                        url="https://example.org/fresh",
                        title=title,
                        summary=title,
                        content=None,
                        author=None,
                        tags=(),
                        language="ru",
                        published_at=datetime.now(UTC),
                        content_hash=content_hash(title, title),
                    )
                ],
            )
        await embed_pending(get_embedder())
        # The cached feed outlives a source's run by a minute at most; here, at once.
        await forget_taste(get_cache(), uuid.UUID(me["id"]))
        after = (await reader.get("/feed/fresh", params={"since": shown["built_at"]})).json()
        reloaded = (await reader.get("/feed", params={"limit": 50, "order": "new"})).json()

    assert before == {"fresh": 0}
    assert marked == {"fresh": 0}
    assert after == {"fresh": 1}
    assert reloaded["snapshot"] != shown["snapshot"]
    assert reloaded["items"][0]["title"] == title


async def test_the_feed_tells_which_articles_have_a_picture_as_of_each_page(api: str) -> None:
    from sqlalchemy import update

    from radar.db import session_scope
    from radar.db.models import Article

    ids = await seed_articles()
    async with register(api) as reader:
        await reader.post("/profiles", json=profile_spec())
        first = (await reader.get("/feed", params={"limit": 50})).json()
        # The picture is found after the feed was ranked, as the page reader does.
        async with session_scope() as session:
            await session.execute(
                update(Article)
                .where(Article.id == ids["vpn"])
                .values(image_url="https://example.org/pics/vpn.png")
            )
        again = (
            await reader.get("/feed", params={"limit": 50, "snapshot": first["snapshot"]})
        ).json()

    def pictured(page: dict[str, list[dict[str, object]]]) -> set[object]:
        return {item["article_id"] for item in page["items"] if item["has_picture"]}

    assert again["snapshot"] == first["snapshot"]
    assert pictured(first) == set()
    assert pictured(again) == {ids["vpn"]}


async def test_a_post_shows_the_articles_own_picture_fetched_once(
    api: str, site: dict[str, object]
) -> None:
    from sqlalchemy import update

    from radar.db import session_scope
    from radar.db.models import Article

    pictured = await article(STORY)
    bare = await article("https://news.example/bare")
    async with session_scope() as session:
        await session.execute(update(Article).where(Article.id == bare).values(image_url=None))

    async with register(api) as reader:
        first = await reader.get(f"/articles/{pictured}/picture")
        second = await reader.get(f"/articles/{pictured}/picture")
        none = await reader.get(f"/articles/{bare}/picture")

    assert (first.status_code, first.content) == (200, PNG)
    assert first.headers["content-type"] == "image/png"
    assert second.content == PNG
    assert site["hits"]["/pics/lead.jpg"] == 1
    assert none.status_code == 404


async def test_a_shown_article_gets_the_picture_its_feed_did_not_carry(
    api: str, site: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy import select, update

    from radar.db import session_scope
    from radar.db.models import Article
    from radar.ingest import measure

    monkeypatch.setattr(measure, "build_client", site["client"])
    # Timed from the feed's full text, but with no picture: read for the picture alone.
    article_id = await article(STORY)
    async with session_scope() as session:
        await session.execute(
            update(Article).where(Article.id == article_id).values(image_url=None, word_count=321)
        )

    await measure.measure([article_id])

    async with session_scope() as session:
        found = (
            await session.execute(
                select(Article.image_url, Article.word_count).where(Article.id == article_id)
            )
        ).one()
    assert found == ("https://news.example/pics/lead.jpg", 321)


async def test_a_page_without_a_picture_is_not_read_again_for_it_soon(
    api: str, site: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import update

    from radar.db import session_scope
    from radar.db.models import Article
    from radar.ingest import measure

    monkeypatch.setattr(measure, "build_client", site["client"])
    lead = '<meta property="og:image" content="https://news.example/pics/lead.jpg">'
    page = PAGE.replace(lead, "")
    site["page"] = httpx.Response(200, html=page)
    article_id = await article(STORY)
    async with session_scope() as session:
        await session.execute(
            update(Article).where(Article.id == article_id).values(image_url=None, word_count=321)
        )

    now = datetime.now(UTC)
    await measure.measure([article_id], now=now)
    # Past the three days after which a failed page is tried again.
    await measure.measure([article_id], now=now + timedelta(days=4))

    assert site["hits"]["/story"] == 1
