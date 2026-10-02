# ruff: noqa: F811  (the fixtures are imported from the other tests)
"""The feed's two looks: the reader's choice, and the pictures the Telegram look shows.

Needs PostgreSQL; skipped without it.
"""

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


async def test_the_look_of_the_feed_is_kept_with_the_account(api: str) -> None:
    async with register(api) as reader:
        before = (await reader.get("/auth/me")).json()["feed_view"]
        chosen = await reader.patch("/auth/me/settings", json={"feed_view": "telegram"})
        after = (await reader.get("/auth/me")).json()["feed_view"]
        unknown = await reader.patch("/auth/me/settings", json={"feed_view": "grid"})

    assert before == "cards"
    assert chosen.json() == {"feed_view": "telegram"}
    assert after == "telegram"
    assert unknown.status_code == 422


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
