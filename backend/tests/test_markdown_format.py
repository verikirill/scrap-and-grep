# ruff: noqa: F811  (the digest fixture is imported from test_render)
"""Markdown is the main format of a digest (QA with the jury): metadata a
program can read, a table of contents, cards as tables and what was left
out, folded, all as GitLab renders it."""

import yaml

from radar.domain import AttackCard, VulnerabilityCard
from radar.render.markdown import gitlab_anchor, render_markdown
from radar.views import DigestView, TopicView
from tests.test_render import _item, digest  # noqa: F401  (fixtures)

KEYS = {
    "profile",
    "profile_version",
    "audience",
    "period_start",
    "period_end",
    "generated",
    "llm",
    "embedding",
    "sources",
    "publications",
    "candidates",
    "entries",
    "manual_minutes",
}


def _front_matter(markdown: str) -> dict[str, object]:
    first, body, _ = markdown.split("---\n", 2)
    assert first == ""
    data: dict[str, object] = yaml.safe_load(body)
    return data


def test_the_digest_opens_with_metadata_a_program_can_read(digest: DigestView) -> None:
    data = _front_matter(render_markdown(digest))

    assert set(data) == KEYS
    assert data["profile"] == "ИБ АСУ ТП"
    assert data["audience"] == "specialist"
    assert data["period_start"] == "2026-09-23"
    assert data["publications"] == 800
    assert data["entries"] == 2
    # 800 publications at 1.3 s and 2 entries at 4.6 min, the pace the issue states.
    assert data["manual_minutes"] == 27


def test_a_profile_name_with_quotes_colons_and_a_line_break_stays_valid_yaml(
    digest: DigestView,
) -> None:
    name = 'Руководство: "ИБ"\nи ИТ'

    data = _front_matter(render_markdown(digest.model_copy(update={"profile_name": name})))

    assert data["profile"] == name


def test_anchors_follow_gitlab() -> None:
    seen: dict[str, int] = {}

    assert gitlab_anchor("1. Атаки", seen) == "1-атаки"
    assert gitlab_anchor("2. Уязвимости", seen) == "2-уязвимости"
    assert gitlab_anchor("Разное", seen) == "разное"
    assert gitlab_anchor("Разное", seen) == "разное-1"
    assert gitlab_anchor("Разное", seen) == "разное-2"
    # As git.codenrock.com renders it: a run of hyphens stays, an underscore too.
    assert gitlab_anchor("АСУ ТП: «новое» - и старое", seen) == "асу-тп-новое---и-старое"
    assert gitlab_anchor("Snake_case и 3.5 -- двойной", seen) == "snake_case-и-35----двойной"


def test_a_specialist_gets_a_table_of_contents(digest: DigestView) -> None:
    two = digest.model_copy(
        update={"topics": [*digest.topics, TopicView(title="Атаки", overview="", items=[])]}
    )

    markdown = render_markdown(two)

    assert "- [1. АСУ ТП](#1-асу-тп)" in markdown
    assert "- [2. Атаки](#2-атаки)" in markdown
    assert markdown.index("## Содержание") < markdown.index("## 1. АСУ ТП")


def test_management_gets_no_table_of_contents(digest: DigestView) -> None:
    management = digest.model_copy(
        update={"profile": digest.profile.model_copy(update={"audience": "management"})}
    )

    assert "## Содержание" not in render_markdown(management)


def test_a_card_is_a_table_and_a_pipe_in_a_value_cannot_break_it(digest: DigestView) -> None:
    card = _item(9, "Атака на ПЛК", kind="attack", attack=AttackCard(group="Sandworm | APT44"))
    with_card = digest.model_copy(
        update={"topics": [TopicView(title="Атаки", overview="", items=[card])]}
    )

    markdown = render_markdown(with_card)

    assert "| Поле | Значение |" in markdown
    assert "| --- | --- |" in markdown
    assert "| Группировка | Sandworm \\| APT44 |" in markdown


def test_a_version_bound_in_a_card_reads_as_written(digest: DigestView) -> None:
    card = _item(
        9,
        "Armatura One: удалённое выполнение кода",
        kind="vulnerability",
        vulnerability=VulnerabilityCard(
            affected="Armatura One <4.7.2", fix="Обновить PCM600 до версии > 2.14"
        ),
    )
    with_card = digest.model_copy(
        update={"topics": [TopicView(title="Уязвимости", overview="", items=[card])]}
    )

    markdown = render_markdown(with_card)

    assert "| Затронуто | Armatura One \\<4.7.2 |" in markdown
    assert "| Обновление | Обновить PCM600 до версии \\> 2.14 |" in markdown
    assert "&lt;" not in markdown
    assert "&gt;" not in markdown


def test_what_was_left_out_is_folded_with_its_reasons(digest: DigestView) -> None:
    rejected = _item(7, "Вакансия инженера", reject_reason="low_score", score=0.21)

    markdown = render_markdown(digest.model_copy(update={"rejected": [rejected]}))

    assert "<details><summary>Не вошло в выпуск: 1</summary>" in markdown
    block = markdown[markdown.index("<details>") : markdown.index("</details>")]
    # A blank line after the summary, or GitLab leaves the list as plain text.
    assert "</summary>\n\n- " in block
    assert "[Вакансия инженера](https://example.org/a/7)" in block
    assert "0.21" in block
    assert "ниже порога релевантности" in block


def test_nothing_left_out_means_no_block(digest: DigestView) -> None:
    assert "<details>" not in render_markdown(digest)
