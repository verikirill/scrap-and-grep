"""A reader hides card rows they do not need: the page, the reports and the
letter leave them out, while the card itself stays as the model and the check
made it."""

from io import BytesIO
from typing import Any

import pytest
from docx import Document
from pydantic import ValidationError

from radar.cards import card_fields
from radar.domain import (
    CARD_FIELD_KEYS,
    AttackCard,
    AttackTechnique,
    ProfileSpec,
    VulnerabilityCard,
    VulnerabilityReference,
)
from radar.render.docx import render_docx
from radar.render.markdown import render_markdown
from radar.views import digest_view
from tests.test_systems import _digest, _entry

VULNERABILITY = {
    "vulnerability": {
        "name": "Обход аутентификации в Cisco ASA",
        "affected": "Cisco ASA 9.16-9.20",
        "fix": "версия 9.20.3",
        "workaround": "отключить WebVPN",
        "exploit": "public",
        "ids": ["CVE-2026-1111"],
        "cvss_score": "9.8",
        "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        "cwe": ["CWE-287"],
        "impact": "захват устройства",
    }
}


def _profile(**extra: object) -> ProfileSpec:
    return ProfileSpec.model_validate(
        {"name": "ИБ", "interests": [{"id": "ics", "title": "АСУ ТП"}], **extra}
    )


def _vulnerability_digest(hidden: list[str]) -> Any:
    entry = _entry(1, "Уязвимость в Cisco ASA", 0, VULNERABILITY)
    entry.kind = "vulnerability"
    entry.priority = "high"
    entry.summary = "Ошибка в WebVPN позволяет войти без пароля."
    entry.why = "Cisco ASA стоит на периметре подстанций."
    digest = _digest((), [entry])
    digest.profile_spec = {**digest.profile_spec, "hidden_card_fields": hidden}
    return digest


def test_a_profile_shows_every_card_row_by_default() -> None:
    assert _profile().hidden_card_fields == ()


def test_a_profile_keeps_each_hidden_row_once() -> None:
    profile = _profile(hidden_card_fields=["attack.group", "vulnerability.cwe", "attack.group"])

    assert profile.hidden_card_fields == ("attack.group", "vulnerability.cwe")


@pytest.mark.parametrize("key", ["attack.colour", "group", "vulnerability.summary", ""])
def test_a_profile_refuses_a_row_no_card_has(key: str) -> None:
    with pytest.raises(ValidationError):
        _profile(hidden_card_fields=[key])


def test_hiding_rows_does_not_change_how_publications_are_graded() -> None:
    shown = _profile()
    hidden = _profile(hidden_card_fields=["vulnerability.cvss", "attack.indicators"])

    assert hidden.fingerprint() == shown.fingerprint()


def test_every_key_a_reader_may_hide_names_a_card_row() -> None:
    reference = VulnerabilityReference(id="CVE-2026-1111", found=True, epss=0.4)
    attack = AttackCard(
        techniques=(AttackTechnique(id="T1566", name="Phishing"),), indicators=("1.2.3[.]4",)
    )
    vulnerability = VulnerabilityCard(
        cvss_score="9.8",
        cvss_vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        equipment="Siemens S7-1500",
        protocols="Profinet",
    )

    keys = {key for key, _, _ in card_fields(attack, None, [reference])}
    keys |= {key for key, _, _ in card_fields(None, vulnerability, [reference])}

    assert keys == set(CARD_FIELD_KEYS)


def test_a_hidden_row_leaves_the_others_in_order() -> None:
    card = VulnerabilityCard(cvss_score="9.8", cvss_vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N")
    hidden = ("vulnerability.cvss", "vulnerability.cvss_words", "vulnerability.fix")

    labels = [label for _, label, _ in card_fields(None, card, [], hidden)]

    assert labels == [
        "Уязвимость",
        "Затронуто",
        "Временные меры",
        "Эксплойт",
        "Идентификаторы",
        "CWE",
        "Последствия",
    ]


def test_news_has_no_card_rows_to_hide() -> None:
    assert card_fields(None, None, [], ("attack.group",)) == []


def test_the_page_leaves_out_the_rows_the_profile_hides() -> None:
    digest = _vulnerability_digest(["vulnerability.cvss", "vulnerability.workaround"])

    view = digest_view(digest)

    item = view.topics[0].items[0]
    labels = [field.label for field in item.fields]
    assert "CVSS" not in labels
    assert "Временные меры" not in labels
    assert labels[:3] == ["Уязвимость", "Затронуто", "Обновление"]
    assert item.hidden_fields == ["vulnerability.cvss", "vulnerability.workaround"]
    # The card itself is untouched: hiding is presentation alone.
    assert item.vulnerability is not None
    assert item.vulnerability.cvss_score == "9.8"
    assert item.vulnerability.workaround == "отключить WebVPN"


def test_the_profile_as_it_is_now_overrides_the_one_the_issue_was_built_for() -> None:
    digest = _vulnerability_digest(["vulnerability.cvss"])

    now = digest_view(digest, ("vulnerability.cwe",))
    everything = digest_view(digest, ())

    labels = [field.label for field in now.topics[0].items[0].fields]
    assert "CVSS" in labels
    assert "CWE" not in labels
    assert now.hidden_card_fields == ["vulnerability.cwe"]
    assert "CVSS" in [field.label for field in everything.topics[0].items[0].fields]


def test_the_markdown_report_leaves_out_hidden_rows_and_keeps_the_entry() -> None:
    digest = _vulnerability_digest(["vulnerability.cvss", "vulnerability.ids"])

    markdown = render_markdown(digest_view(digest))

    assert "| CVSS |" not in markdown
    assert "| Идентификаторы |" not in markdown
    assert "| Обновление | версия 9.20.3 |" in markdown
    # The headline, the summary, the priority and why it matters always stay.
    assert "[Уязвимость в Cisco ASA]" in markdown
    assert "Ошибка в WebVPN позволяет войти без пароля." in markdown
    assert "приоритет: высокий" in markdown
    assert "**Почему важно:** Cisco ASA стоит на периметре подстанций." in markdown


def test_the_word_report_leaves_out_hidden_rows() -> None:
    digest = _vulnerability_digest(["vulnerability.impact"])

    document = Document(BytesIO(render_docx(digest_view(digest))))

    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "Обновление: версия 9.20.3" in text
    assert "Последствия" not in text
    assert "захват устройства" not in text


def test_a_saved_profile_without_the_setting_reads_with_every_row() -> None:
    digest = _vulnerability_digest([])
    del digest.profile_spec["hidden_card_fields"]

    labels = [field.label for field in digest_view(digest).topics[0].items[0].fields]

    assert {"CVSS", "Временные меры", "Идентификаторы"} <= set(labels)
