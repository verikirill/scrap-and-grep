# ruff: noqa: F811  (the fixtures are imported from the other tests)
"""Search in the publications: by words first, then by meaning.

Needs PostgreSQL; skipped without it.
"""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from tests.test_accounts_api import api, database  # noqa: F401

pytestmark = pytest.mark.integration

MODEL = "test:search"


def unit(vector: np.ndarray) -> list[float]:
    return (vector / np.linalg.norm(vector)).tolist()


async def seed(rng: np.random.Generator) -> tuple[list[float], dict[str, int]]:
    """Sixty unrelated articles, one about the query in other words, one
    with the query's words, one that names a CVE."""
    from radar.config import EMBEDDING_DIM
    from radar.db import session_scope
    from radar.db.models import Source
    from radar.store.articles import NewArticle, insert_new, save_embeddings
    from radar.text import content_hash

    async with session_scope() as session:
        source = Source(
            slug="search-test",
            name="Тестовая лента",
            feed_url="https://example.org/search",
            category="security",
        )
        session.add(source)
        await session.flush()
        source_id = source.id

    query = rng.normal(size=EMBEDDING_DIM)
    now = datetime.now(UTC)
    titles = {
        "words": "Атака на подстанцию в Европе",
        "meaning": "Энергообъект остановлен после вторжения в сеть",
        "cve": "Эксплойт для CVE-2026-11111 в шлюзе",
        **{f"noise-{i}": f"Новость о разном номер {i}" for i in range(60)},
    }
    vectors = {
        "words": unit(rng.normal(size=EMBEDDING_DIM)),
        "meaning": unit(query + 0.2 * rng.normal(size=EMBEDDING_DIM)),
        "cve": unit(rng.normal(size=EMBEDDING_DIM)),
        **{f"noise-{i}": unit(rng.normal(size=EMBEDDING_DIM)) for i in range(60)},
    }
    items = [
        NewArticle(
            url=f"https://example.org/search/{key}",
            title=title,
            summary=title,
            content=None,
            author=None,
            tags=(),
            language="ru",
            published_at=now - timedelta(hours=index),
            content_hash=content_hash(title, key),
        )
        for index, (key, title) in enumerate(titles.items())
    ]
    async with session_scope() as session:
        ids = await insert_new(session, source_id, items)
    by_key = dict(zip(titles, ids, strict=True))
    async with session_scope() as session:
        await save_embeddings(session, MODEL, [(by_key[key], vectors[key]) for key in titles])
    return unit(query), by_key


async def test_words_come_first_and_meaning_follows_marked(api: str) -> None:
    from radar.db import session_scope
    from radar.store.articles import ArticleFilter, Meaning, find_articles

    query, ids = await seed(np.random.default_rng(7))
    meaning = Meaning(vector=query, model=MODEL, floor=0.38)

    async with session_scope() as session:
        found, total = await find_articles(
            session, ArticleFilter(query="атака на подстанцию"), 10, 0, meaning
        )

    assert [(article.id, by_meaning) for article, by_meaning in found] == [
        (ids["words"], False),
        (ids["meaning"], True),
    ]
    assert total == 2


async def test_an_identifier_is_looked_up_only_as_written(api: str) -> None:
    from radar.db import session_scope
    from radar.store.articles import ArticleFilter, Meaning, find_articles

    query, ids = await seed(np.random.default_rng(8))
    meaning = Meaning(vector=query, model=MODEL, floor=0.38)

    async with session_scope() as session:
        found, total = await find_articles(
            session, ArticleFilter(query="CVE-2026-11111"), 10, 0, meaning
        )

    # The article close in meaning has no such CVE and stays out.
    assert [article.id for article, _ in found] == [ids["cve"]]
    assert total == 1


async def test_nothing_close_enough_adds_nothing(api: str) -> None:
    from radar.db import session_scope
    from radar.store.articles import ArticleFilter, Meaning, find_articles

    query, _ = await seed(np.random.default_rng(9))
    elsewhere = np.random.default_rng(10).normal(size=len(query))
    meaning = Meaning(vector=unit(elsewhere), model=MODEL, floor=0.38)

    async with session_scope() as session:
        found, total = await find_articles(
            session, ArticleFilter(query="цифровая подстанция МЭК 61850"), 10, 0, meaning
        )

    assert found == []
    assert total == 0


async def test_a_page_past_the_word_matches_continues_with_meaning(api: str) -> None:
    from radar.db import session_scope
    from radar.store.articles import ArticleFilter, Meaning, find_articles

    query, ids = await seed(np.random.default_rng(11))
    meaning = Meaning(vector=query, model=MODEL, floor=0.38)

    async with session_scope() as session:
        first, total = await find_articles(
            session, ArticleFilter(query="атака на подстанцию"), 1, 0, meaning
        )
        second, _ = await find_articles(
            session, ArticleFilter(query="атака на подстанцию"), 1, 1, meaning
        )

    assert total == 2
    assert [article.id for article, _ in first] == [ids["words"]]
    assert [(article.id, by_meaning) for article, by_meaning in second] == [(ids["meaning"], True)]
