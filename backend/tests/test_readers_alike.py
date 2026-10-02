# ruff: noqa: F811  (the fixtures are imported from the other tests)
"""The vectors behind "readers alike". Needs PostgreSQL; skipped without it."""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from tests.test_accounts_api import api, database  # noqa: F401
from tests.test_search import MODEL, seed

pytestmark = pytest.mark.integration


async def test_the_mean_article_vector_of_a_period_comes_back_as_numbers(api: str) -> None:
    # Every reader's taste is centred on this mean before readers are compared.
    from sqlalchemy import select

    from radar.db import session_scope
    from radar.db.models import ArticleEmbedding
    from radar.recsys import store

    await seed(np.random.default_rng(3))
    async with session_scope() as session:
        stored = await session.scalars(
            select(ArticleEmbedding.embedding).where(ArticleEmbedding.model == MODEL)
        )
        vectors = np.asarray(list(stored), dtype=np.float32)
        mean = await store.corpus_mean(session, MODEL, datetime.now(UTC) - timedelta(days=7))

    assert mean is not None
    np.testing.assert_allclose(mean, vectors.mean(axis=0), atol=1e-5)
