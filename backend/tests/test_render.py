"""Exports must carry every source link, in both formats."""

import re
import uuid
from datetime import UTC, datetime
from io import BytesIO

import pytest
from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE
from markdown_it import MarkdownIt

from radar.domain import Interest, ProfileSpec
from radar.render.docx import render_docx
from radar.render.markdown import render_markdown
from radar.views import DigestView, DuplicateView, ItemView, TopicView, read_via

PUBLISHED = datetime(2026, 9, 29, 21, 30, tzinfo=UTC)

# GitLab renders Markdown by CommonMark and lets raw HTML through, so the
# export is checked as such a renderer reads it, not as a string.
COMMONMARK = MarkdownIt("commonmark", {"html": True}).enable("table")


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
    assert "[Зеркало](https://mirror.example/x%281%29)" in text
    assert "**Почему важно:** Нужно обновить контроллеры." in text


def test_text_from_articles_and_the_model_cannot_add_links_or_html(digest: DigestView) -> None:
    hostile = _item(
        3,
        "Заголовок](https://evil.example) [ещё",
        summary="Читайте [здесь](https://evil.example) <img src=x onerror=alert(1)>",
        why="`код` и <script>alert(1)</script>",
    )
    topic = TopicView(title="Тема <b>жирная</b>", overview="", items=[hostile])

    text = render_markdown(digest.model_copy(update={"topics": [topic]}))

    # A closing bracket that is not escaped would end the link text early.
    assert re.search(r"(?<!\\)\]\(https://evil", text) is None
    html = COMMONMARK.render(text)
    assert "<img" not in html
    assert "<script>" not in html
    assert "<b>" not in html
    assert "(https://example.org/a/3)" in text


def test_a_tag_in_a_title_reads_as_text_and_never_becomes_html(digest: DigestView) -> None:
    hostile = _item(4, "<script>alert(1)</script> в SCADA", title="<script>alert(2)</script>")
    topic = TopicView(title="АСУ ТП", overview="", items=[hostile])

    text = render_markdown(digest.model_copy(update={"topics": [topic]}))
    html = COMMONMARK.render(text)

    # Escaped by a backslash, not by an entity: the raw file reads as written.
    assert "\\<script\\>alert(1)\\</script\\> в SCADA" in text
    assert "&lt;" not in text
    assert "<script" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt; в SCADA</a>" in html
    assert "Оригинал: &lt;script&gt;alert(2)&lt;/script&gt;" in html


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


def test_management_reads_what_it_means_for_the_company_first(digest: DigestView) -> None:
    management = digest.model_copy(
        update={
            "profile": digest.profile.model_copy(update={"audience": "management"}),
            "implications": ["Проверить доступы подрядчиков.", "Обновить план реагирования."],
        }
    )

    markdown = render_markdown(management)
    paragraphs = [
        paragraph.text for paragraph in Document(BytesIO(render_docx(management))).paragraphs
    ]

    assert markdown.index("## Что это значит для нас") < markdown.index("## Главное")
    assert "- Проверить доступы подрядчиков." in markdown
    assert paragraphs.index("Что это значит для нас") < paragraphs.index("Главное")
    assert "Обновить план реагирования." in paragraphs


def test_a_specialist_gets_no_block_for_management(digest: DigestView) -> None:
    specialist = digest.model_copy(update={"implications": ["Лишнее."]})

    assert "Что это значит для нас" not in render_markdown(specialist)


def test_an_entry_says_how_its_protected_source_is_read(digest: DigestView) -> None:
    digest.topics[0].items.append(
        _item(9, "БДУ АСУ ТП: новая уязвимость", source_read_via=read_via("browser", False))
    )

    markdown = render_markdown(digest)

    assert "Источник (прочитан: браузер)" in markdown
    assert read_via("impersonate", True) == "отпечаток Chrome, через прокси"
    assert read_via("plain", False) == ""
