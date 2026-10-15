"""A reader hides whole blocks of the digest page: the reports and the letter
leave them out as well, while the entries, the title and "Главное" stay."""

from io import BytesIO
from typing import Any

import pytest
from docx import Document
from pydantic import ValidationError

from radar.api.routes.digests import _export_key
from radar.domain import AUDIENCE_BLOCKS, DIGEST_BLOCK_KEYS, Interest, ProfileSpec
from radar.render.docx import render_docx
from radar.render.markdown import render_markdown
from radar.views import digest_view, shown_view
from tests.test_card_fields import VULNERABILITY
from tests.test_systems import _digest, _entry

CHANGE = {
    "id": "CVE-2026-1111",
    "headline": "Уязвимость в Cisco ASA",
    "url": "https://example.org/1",
    "since": "2026-10-01",
    "what": ["попала в каталог CISA KEV"],
}


def _profile(**extra: Any) -> ProfileSpec:
    return ProfileSpec(name="ИБ", interests=(Interest(id="ics", title="АСУ ТП"),), **extra)


def _specialist(hidden: list[str]) -> Any:
    """An issue with every block a specialist's report has: the handwork, the
    plan for the shift, what changed, what was left out and how it was made."""
    entry = _entry(1, "Уязвимость в Cisco ASA", 0, VULNERABILITY)
    entry.kind = "vulnerability"
    entry.priority = "high"
    entry.summary = "Ошибка в WebVPN позволяет войти без пароля."
    left_out = _entry(2, "Обзор рынка SIEM", 0, {})
    left_out.selected = False
    left_out.topic_id = None
    left_out.reject_reason = "low_score"
    digest = _digest((), [entry, left_out])
    digest.highlights = ["Срочно обновить Cisco ASA."]
    digest.stats = {"window_total": 300, "selected": 1, "sources": 5, "changes": [CHANGE]}
    digest.profile_spec = {**digest.profile_spec, "hidden_digest_blocks": hidden}
    return digest


def _management(hidden: list[str]) -> Any:
    entry = _entry(1, "Атака на сетевую компанию", 0, {"tags": ["energy", "ru"]})
    digest = _digest((), [entry])
    digest.highlights = ["Атаки на энергетику стали чаще."]
    digest.implications = ["Проверить подрядчиков с удалённым доступом."]
    digest.stats = {"window_total": 300, "selected": 1}
    digest.profile_spec = {
        **digest.profile_spec,
        "audience": "management",
        "hidden_digest_blocks": hidden,
    }
    return digest


def test_a_profile_shows_every_block_by_default() -> None:
    assert _profile().hidden_digest_blocks == ()


def test_a_profile_keeps_each_hidden_block_once() -> None:
    profile = _profile(hidden_digest_blocks=["plan", "short", "plan"])

    assert profile.hidden_digest_blocks == ("plan", "short")


@pytest.mark.parametrize("key", ["highlights", "topics", "title", "Plan", ""])
def test_a_profile_refuses_a_block_the_page_does_not_have(key: str) -> None:
    with pytest.raises(ValidationError):
        _profile(hidden_digest_blocks=[key])


def test_hiding_blocks_does_not_change_how_publications_are_graded() -> None:
    hidden = _profile(hidden_digest_blocks=["risk_matrix", "numbers", "ask"])

    assert hidden.fingerprint() == _profile().fingerprint()


def test_each_block_belongs_to_some_audience() -> None:
    every = {key for blocks in AUDIENCE_BLOCKS.values() for key in blocks}

    assert every == set(DIGEST_BLOCK_KEYS)
    assert "plan" not in AUDIENCE_BLOCKS["management"]
    assert "numbers" not in AUDIENCE_BLOCKS["specialist"]


def test_the_markdown_report_has_every_block_by_default() -> None:
    markdown = render_markdown(digest_view(_specialist([])))

    assert "*Вместо ручной работы:" in markdown
    assert "## План на смену" in markdown
    assert "## Что изменилось с прошлых выпусков" in markdown
    assert "Не вошло в выпуск: 1" in markdown
    assert "## Как составлен выпуск" in markdown


def test_the_markdown_report_leaves_out_hidden_blocks_and_keeps_the_entries() -> None:
    hidden = ["manual", "plan", "changes", "rejected", "method"]

    markdown = render_markdown(digest_view(_specialist(hidden)))

    assert "Вместо ручной работы" not in markdown
    assert "План на смену" not in markdown
    assert "Что изменилось" not in markdown
    assert "Не вошло в выпуск" not in markdown
    assert "Как составлен выпуск" not in markdown
    # The title, "Главное" and the entries always stay.
    assert "# Выпуск" in markdown
    assert "## Главное" in markdown
    assert "- Срочно обновить Cisco ASA." in markdown
    assert "### [Уязвимость в Cisco ASA]" in markdown
    assert "Ошибка в WebVPN позволяет войти без пароля." in markdown


def test_the_word_report_leaves_out_hidden_blocks() -> None:
    view = digest_view(_specialist(["plan", "manual", "method"]))

    document = Document(BytesIO(render_docx(view)))

    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "План на смену" not in text
    assert "Вместо ручной работы" not in text
    assert "Как составлен выпуск" not in text
    assert "Что изменилось с прошлых выпусков" in text
    assert "Срочно обновить Cisco ASA." in text


def test_a_management_report_leaves_out_what_it_means_and_the_numbers() -> None:
    view = digest_view(_management([]))
    shown = render_markdown(view)
    hidden = render_markdown(digest_view(_management(["implications", "numbers"])))

    assert view.numbers
    assert "## Что это значит для нас" in shown
    assert f"## {view.numbers_title}" in shown
    assert "Что это значит для нас" not in hidden
    assert "Проверить подрядчиков" not in hidden
    assert view.numbers_title not in hidden
    assert "## Главное" in hidden
    assert "Атака на сетевую компанию" in hidden


def test_the_profile_as_it_is_now_decides_which_blocks_show() -> None:
    digest = _specialist(["plan"])

    now = shown_view(digest, _profile(hidden_digest_blocks=["changes"]))
    gone = shown_view(digest, None)

    assert now.hidden_digest_blocks == ["changes"]
    assert gone.hidden_digest_blocks == ["plan"]
    # The data stays in the view, only the renderers and the page leave it out.
    assert now.plan
    assert not now.shows("changes")
    assert now.shows("plan")


def test_a_saved_profile_without_the_setting_reads_with_every_block() -> None:
    digest = _specialist([])
    del digest.profile_spec["hidden_digest_blocks"]

    assert digest_view(digest).hidden_digest_blocks == []


def test_a_report_with_hidden_blocks_is_cached_apart() -> None:
    everything = digest_view(_specialist([]))
    without_plan = digest_view(_specialist(["plan"]))
    without_changes = digest_view(_specialist(["changes"]))

    keys = {_export_key(view, "md") for view in (everything, without_plan, without_changes)}

    assert len(keys) == 3
    assert _export_key(everything, "md") == f"export:{everything.id}:md"
