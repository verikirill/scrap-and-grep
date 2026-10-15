# ruff: noqa: F811  (the fixtures are imported from the other tests)
"""An English article in the reader: translated by the model once, stored for
every next reader, and shown in the original when there is no translation.

Needs PostgreSQL; skipped without it.
"""

from datetime import UTC, datetime

import pytest

from radar.ai.resilient import CircuitBreaker
from radar.reader.blocks import Block
from tests.test_accounts_api import api, database, register  # noqa: F401
from tests.test_translate import (
    ADVISORY,
    COMMAND,
    EDITORS_NOTE,
    TITLE,
    FakeChat,
    article_blocks,
    drop_digits,
    drop_tags,
)

pytestmark = pytest.mark.integration


async def stored_article(title: str, blocks: list[Block], *, language: str = "en") -> int:
    """An article whose page was read already: the reader shows these blocks."""
    from radar.db import session_scope
    from radar.db.models import ArticleBody, Source
    from radar.reader.service import READER_VERSION
    from radar.store.articles import NewArticle, insert_new
    from radar.text import content_hash

    url = f"https://news.example/{content_hash(title, language)[:12]}"
    async with session_scope() as session:
        source = Source(
            slug=f"translate-{content_hash(url, '')[:8]}",
            name="Security News",
            feed_url=f"{url}/feed",
            category="security",
            language=language,
        )
        session.add(source)
        await session.flush()
        [article_id] = await insert_new(
            session,
            source.id,
            [
                NewArticle(
                    url=url,
                    title=title,
                    summary="",
                    content=None,
                    author=None,
                    tags=(),
                    language=language,
                    published_at=datetime.now(UTC),
                    content_hash=content_hash(url, "x"),
                    image_url=None,
                )
            ],
        )
        session.add(
            ArticleBody(
                article_id=article_id,
                version=READER_VERSION,
                status="page",
                blocks=blocks,
                images={"0123456789abcdef": "https://news.example/pics/admin.png"},
                read_at=datetime.now(UTC),
            )
        )
    return article_id


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """The model the reader asks, and a breaker of its own for the test."""
    from radar.api.routes import reader as reader_routes

    state: dict[str, object] = {"chat": FakeChat(), "breaker": CircuitBreaker(3, 30)}
    monkeypatch.setattr(reader_routes, "get_chat", lambda: state["chat"])
    monkeypatch.setattr(reader_routes, "get_breaker", lambda: state["breaker"])
    return state


async def test_an_english_article_is_translated_once_and_read_from_the_database_after(
    api: str, model: dict[str, object]
) -> None:
    from sqlalchemy import select

    from radar.db import session_scope
    from radar.db.models import ArticleTranslation

    chat = model["chat"]
    assert isinstance(chat, FakeChat)
    article_id = await stored_article(TITLE, article_blocks())

    async with register(api) as reader:
        read = (await reader.get(f"/articles/{article_id}")).json()
        first = await reader.get(f"/articles/{article_id}/translation", params={"to": "ru"})
        again = await reader.get(f"/articles/{article_id}/translation")
    async with register(api, "another") as another:
        theirs = await another.get(f"/articles/{article_id}/translation")

    assert read["text_language"] == "en"
    assert first.status_code == 200, first.text
    translated = first.json()
    assert translated["status"] == "translated"
    assert translated["source_language"] == "en"
    assert translated["language"] == "ru"
    assert translated["title"] == "Microsoft закрыла CVE-2026-21345 в Exchange Server"
    assert translated["kept_original"] == 0
    blocks = translated["blocks"]
    assert [block["type"] for block in blocks] == [block["type"] for block in read["blocks"]]
    assert blocks[1]["spans"][3] == {"text": "бюллетень", "href": ADVISORY}
    assert " 1 200 серверов" in blocks[1]["spans"][2]["text"]
    assert blocks[4] == {"type": "code", "text": COMMAND}
    assert blocks[7] == {"type": "p", "spans": [{"text": EDITORS_NOTE}]}
    # One request to the model, for every reader that opens the article.
    assert len(chat.prompts) == 1
    assert again.json() == translated
    assert theirs.json() == translated
    async with session_scope() as session:
        row = await session.scalar(select(ArticleTranslation))
    assert row is not None
    assert (row.article_id, row.language, row.source_language) == (article_id, "ru", "en")
    assert row.model == "ollama:fake"


async def test_a_page_read_again_with_new_text_is_translated_again(
    api: str, model: dict[str, object]
) -> None:
    from sqlalchemy import update

    from radar.db import session_scope
    from radar.db.models import ArticleBody

    chat = model["chat"]
    assert isinstance(chat, FakeChat)
    article_id = await stored_article(TITLE, article_blocks())

    async with register(api) as reader:
        before = (await reader.get(f"/articles/{article_id}/translation")).json()
        changed: list[Block] = [
            *article_blocks(),
            {"type": "p", "spans": [{"text": "Update: the patch was re-released."}]},
        ]
        async with session_scope() as session:
            await session.execute(update(ArticleBody).values(blocks=changed))
        after = (await reader.get(f"/articles/{article_id}/translation")).json()

    assert len(chat.prompts) == 2
    assert len(after["blocks"]) == len(before["blocks"]) + 1
    assert after["blocks"][-1]["spans"][0]["text"].startswith("По-русски: Update")


async def test_a_russian_article_is_not_translated(api: str, model: dict[str, object]) -> None:
    chat = model["chat"]
    assert isinstance(chat, FakeChat)
    blocks: list[Block] = [{"type": "p", "spans": [{"text": EDITORS_NOTE * 3}]}]
    article_id = await stored_article("Microsoft закрыла уязвимость в Exchange", blocks)

    async with register(api) as reader:
        read = (await reader.get(f"/articles/{article_id}")).json()
        answer = (await reader.get(f"/articles/{article_id}/translation")).json()

    assert read["text_language"] == "ru"
    assert answer == {
        "id": article_id,
        "status": "original",
        "source_language": "ru",
        "language": "ru",
        "title": None,
        "blocks": None,
        "kept_original": 0,
        "reason": None,
    }
    assert chat.prompts == []


async def test_without_a_model_the_reader_is_told_and_shown_the_original(
    api: str, model: dict[str, object]
) -> None:
    from radar.reader.translate import NO_MODEL

    model["chat"] = None
    article_id = await stored_article(TITLE, article_blocks())

    async with register(api) as reader:
        answer = (await reader.get(f"/articles/{article_id}/translation")).json()

    assert answer["status"] == "unavailable"
    assert answer["reason"] == NO_MODEL
    assert answer["blocks"] is None
    assert answer["title"] is None


async def test_a_failed_model_gives_no_partial_translation_and_nothing_is_kept(
    api: str, model: dict[str, object]
) -> None:
    from sqlalchemy import func, select

    from radar.db import session_scope
    from radar.db.models import ArticleTranslation
    from radar.reader.translate import NOT_NOW

    breaker = model["breaker"]
    assert isinstance(breaker, CircuitBreaker)
    model["chat"] = FakeChat(error=TimeoutError("the model is slow"))
    article_id = await stored_article(TITLE, article_blocks())

    async with register(api) as reader:
        failed = (await reader.get(f"/articles/{article_id}/translation")).json()
        model["chat"] = FakeChat()
        recovered = (await reader.get(f"/articles/{article_id}/translation")).json()

    assert failed["status"] == "unavailable"
    assert failed["reason"] == NOT_NOW
    assert failed["blocks"] is None
    # The model came back: the next reader gets the translation.
    assert recovered["status"] == "translated"
    assert not breaker.is_open
    async with session_scope() as session:
        assert await session.scalar(select(func.count()).select_from(ArticleTranslation)) == 1


async def test_a_paragraph_the_model_broke_twice_is_shown_in_the_original_and_counted(
    api: str, model: dict[str, object]
) -> None:
    from sqlalchemy import select

    from radar.db import session_scope
    from radar.db.models import ArticleTranslation

    broken = FakeChat(drop_tags)
    model["chat"] = broken
    article_id = await stored_article(TITLE, article_blocks())

    async with register(api) as reader:
        first = (await reader.get(f"/articles/{article_id}/translation")).json()
        again = (await reader.get(f"/articles/{article_id}/translation")).json()

    assert first["status"] == "translated"
    assert first["kept_original"] == 1
    assert first["title"] == "Microsoft закрыла CVE-2026-21345 в Exchange Server"
    assert first["blocks"][1] == article_blocks()[1]
    # Stored with its count: the next reader is told the same without the model.
    assert again == first
    assert len(broken.prompts) == 2
    async with session_scope() as session:
        row = await session.scalar(
            select(ArticleTranslation).where(ArticleTranslation.article_id == article_id)
        )
    assert row is not None
    assert row.kept_original == 1


async def test_a_translation_the_model_broke_twice_is_not_asked_for_again_at_once(
    api: str, model: dict[str, object]
) -> None:
    from radar.cache import get_cache

    if not await get_cache().ping():
        pytest.skip("Valkey is not reachable")
    broken = FakeChat(drop_digits)
    model["chat"] = broken
    breaker = model["breaker"]
    assert isinstance(breaker, CircuitBreaker)
    article_id = await stored_article(TITLE, article_blocks())

    async with register(api) as reader:
        first = (await reader.get(f"/articles/{article_id}/translation")).json()
        second = (await reader.get(f"/articles/{article_id}/translation")).json()

    assert first["status"] == second["status"] == "unavailable"
    # Asked and asked again with its mistakes once, then left alone.
    assert len(broken.prompts) == 2
    # A model that answers is not a model that is down: the digests keep it.
    assert not breaker.is_open


async def test_an_unknown_article_or_language_is_refused(api: str) -> None:
    async with register(api) as reader:
        missing = await reader.get("/articles/999999/translation")
        german = await reader.get("/articles/999999/translation", params={"to": "de"})

    assert missing.status_code == 404
    assert german.status_code == 422
