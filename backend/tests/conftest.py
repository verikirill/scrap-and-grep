"""Shared builders: tests state only what matters for the case at hand."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from radar.domain import (
    ArticleRef,
    Candidate,
    Grade,
    GradedCandidate,
    Interest,
    ProfileSpec,
)
from radar.text import content_hash

ArticleFactory = Callable[..., ArticleRef]
GradedFactory = Callable[..., GradedCandidate]


def pytest_asyncio_loop_factories(
    config: pytest.Config, item: pytest.Item
) -> dict[str, Callable[[], asyncio.AbstractEventLoop]]:
    """Run every async test on a selector loop.

    psycopg's async driver cannot use the proactor loop that Windows picks by
    default; on Linux and macOS the selector loop is the default anyway.
    """
    return {"selector": asyncio.SelectorEventLoop}


@pytest.fixture
def profile() -> ProfileSpec:
    return ProfileSpec(
        name="ИБ АСУ ТП",
        role="Инженер по безопасности подстанций",
        interests=(
            Interest(id="ics", title="Безопасность АСУ ТП", keywords=("SCADA", "АСУ ТП")),
            Interest(id="vuln", title="Уязвимости", keywords=("уязвимость", "CVE")),
        ),
        exclusions=("вакансии",),
        min_score=0.5,
        max_items=5,
    )


@pytest.fixture
def make_article() -> ArticleFactory:
    counter = iter(range(1, 10_000))

    def build(
        title: str, summary: str = "", source: str = "Источник", **extra: object
    ) -> ArticleRef:
        article_id = next(counter)
        return ArticleRef(
            id=article_id,
            url=f"https://example.org/news/{article_id}",
            title=title,
            summary=summary,
            source_name=source,
            source_category="security",
            language="ru",
            published_at=datetime(2026, 9, 29, 10, 0, tzinfo=UTC),
            content_hash=content_hash(title, summary),
            **extra,  # type: ignore[arg-type]
        )

    return build


@pytest.fixture
def make_graded(make_article: ArticleFactory) -> GradedFactory:
    def build(
        title: str,
        score: float,
        *,
        interest_id: str = "ics",
        excluded_by: str | None = None,
        source: str = "Источник",
    ) -> GradedCandidate:
        candidate = Candidate(
            article=make_article(title, source=source),
            interest_id=interest_id,
            retrieval_score=score,
            excluded_by=excluded_by,
        )
        return GradedCandidate(
            candidate=candidate, grade=Grade(relevance=2, interest_id=interest_id), score=score
        )

    return build
