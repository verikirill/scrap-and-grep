"""Exports must carry every source link, in both formats."""

import uuid
from datetime import UTC, datetime
from io import BytesIO

import pytest
from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE

from radar.domain import Interest, ProfileSpec
from radar.render.docx import render_docx
from radar.render.markdown import render_markdown
from radar.views import DigestView, DuplicateView, ItemView, TopicView

PUBLISHED = datetime(2026, 9, 29, 21, 30, tzinfo=UTC)


def _item(article_id: int, headline: str, **extra: object) -> ItemView:
    fields = {
        "article_id": article_id,
        "url": f"https://example.org/a/{article_id}",
        "title": headline,
        "headline": headline,
        "source_name": "Источник",
        "source_category": "security",
        "language": "ru",
        "published_at": PUBLISHED,
        "score": 0.82,
        "retrieval_score": 0.7,
        "relevance": 2,
        "interest_id": "ics",
        "interest_title": "Безопасность АСУ ТП",
        "reason": "",
        "summary": "Краткое изложение.",
        "why": "Нужно обновить контроллеры.",
    }
    return ItemView.model_validate({**fields, **extra})


@pytest.fixture
def digest() -> DigestView:
    profile = ProfileSpec(name="ИБ АСУ ТП", interests=(Interest(id="ics", title="АСУ ТП"),))
    translated = _item(
        2,
        "Siemens закрыла уязвимость [в ПЛК]",
        title="Siemens patches PLC flaw",
        duplicates=[
            DuplicateView(title="То же", url="https://mirror.example/x(1)", source_name="Зеркало")
        ],
    )
    return DigestView(
        id=uuid.UUID(int=1),
        profile_id=None,
        profile_name=profile.name,
        profile_version=3,
        period_start=datetime(2026, 9, 23, tzinfo=UTC),
        period_end=datetime(2026, 9, 30, tzinfo=UTC),
        status="done",
        stage="done",
        progress=1.0,
        error=None,
        title="Главное за неделю",
        stats={
            "window_total": 800,
            "candidates": 60,
            "selected": 2,
            "sources": 2,
            "duplicates_merged": 1,
            "embedding_model": "m",
            "llm": "heuristic",
        },
        created_at=PUBLISHED,
        finished_at=PUBLISHED,
        profile=profile,
        highlights=["Вышел патч для ПЛК."],
        topics=[
            TopicView(title="АСУ ТП", overview="Обзор темы.", items=[_item(1, "Атака"), translated])
        ],
        rejected=[],
    )


def test_markdown_links_every_item_and_duplicate_and_survives_brackets(digest: DigestView) -> None:
    text = render_markdown(digest)

    assert "# Главное за неделю" in text
    assert "## 1. АСУ ТП" in text
    assert "[Атака](https://example.org/a/1)" in text
    assert "[Siemens закрыла уязвимость \\[в ПЛК\\]](https://example.org/a/2)" in text
    assert "Оригинал: Siemens patches PLC flaw" in text
    assert "[Зеркало](https://mirror.example/x(1%29)" in text
    assert "**Почему важно:** Нужно обновить контроллеры." in text


def test_markdown_shows_dates_in_moscow_time(digest: DigestView) -> None:
    # 21:30 UTC on the 29th is already the 30th in Moscow.
    assert "Источник · 30.09.2026" in render_markdown(digest)


def test_docx_opens_and_carries_all_links(digest: DigestView) -> None:
    document = Document(BytesIO(render_docx(digest)))

    links = {
        relation.target_ref
        for relation in document.part.rels.values()
        if relation.reltype == RELATIONSHIP_TYPE.HYPERLINK
    }
    body = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert links == {
        "https://example.org/a/1",
        "https://example.org/a/2",
        "https://mirror.example/x(1)",
    }
    assert "1. АСУ ТП" in body
    assert "Почему важно: Нужно обновить контроллеры." in body


def test_empty_digest_says_so(digest: DigestView) -> None:
    empty = digest.model_copy(update={"topics": [], "highlights": []})

    assert "публикаций по интересам профиля не найдено" in render_markdown(empty)
    assert render_docx(empty)[:2] == b"PK"
