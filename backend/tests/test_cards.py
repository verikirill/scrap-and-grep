"""The organizers' dataset: record kinds, priorities, cards and their check."""

from typing import Any, cast

import pytest
from pydantic import BaseModel

from radar.ai.llm import ModelIntelligence
from radar.cards import (
    check_attack,
    check_entry,
    check_vulnerability,
    defang,
    exploit_evidence,
    priority,
)
from radar.domain import (
    AttackCard,
    Candidate,
    Grade,
    GradedCandidate,
    ItemSummary,
    ProfileSpec,
    RecordKind,
    SelectedItem,
    VulnerabilityCard,
)
from radar.render.markdown import render_markdown
from tests.conftest import ArticleFactory
from tests.test_render import _item, digest  # noqa: F401

BDU_ENTRY = (
    "Уязвимость Citrix NetScaler ADC связана с выходом операции за границы буфера. "
    "CVSS 3.1: AV:N/AC:H/PR:N/UI:N/S:C/C:H/I:H/A:H, базовая оценка 9. "
    "Идентификаторы: CVE: CVE-2026-88772. Эксплойт: существует в открытом доступе. "
    "Используется в атаках. Обновить до версии 14.1-47.48."
)


@pytest.mark.parametrize(
    ("card", "expected"),
    [
        (AttackCard(victim_in_russia=True, energy_sector=True), "high"),
        (AttackCard(victim_in_russia=True, energy_sector=False), "medium"),
        (AttackCard(victim_in_russia=False, energy_sector=True), "low"),
        # A country the text does not name is not taken for Russia.
        (AttackCard(), "low"),
    ],
)
def test_an_attack_ranks_by_the_victim_country_and_the_energy_sector(
    card: AttackCard, expected: str
) -> None:
    assert priority("attack", ItemSummary(summary="", attack=card)) == expected


@pytest.mark.parametrize(
    ("exploit", "expected"),
    [("in_the_wild", "high"), ("public", "high"), ("none", "medium"), ("unknown", "medium")],
)
def test_a_vulnerability_with_an_exploit_ranks_above_one_without(
    exploit: Any, expected: str
) -> None:
    card = VulnerabilityCard(exploit=exploit)
    assert priority("vulnerability", ItemSummary(summary="", vulnerability=card)) == expected
    assert priority("news", ItemSummary(summary="")) is None
    # A management brief has no card, so no priority either.
    assert priority("vulnerability", ItemSummary(summary="")) is None


def test_a_vulnerability_card_keeps_only_what_the_text_says() -> None:
    claimed = VulnerabilityCard(
        ids=("CVE-2026-88772", "CVE-2026-11111"),
        cvss_score="9.8",
        cvss_vector="CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:C/C:H/I:H/A:H",
        fix="Обновить до версии 14.1-47.48",
        affected="NetScaler ADC до 13.0-92.21",
        exploit="unknown",
    )

    checked, removed = check_vulnerability(claimed, BDU_ENTRY)

    assert checked.ids == ("CVE-2026-88772",)
    assert checked.cvss_score == ""
    assert checked.cvss_vector == claimed.cvss_vector
    assert checked.fix == claimed.fix
    assert checked.affected == ""
    # The text says it is used in attacks, whatever the model answered.
    assert checked.exploit == "in_the_wild"
    # The id that went is named: the card still shows the other one.
    assert removed == ["CVE-2026-11111", "Оценка CVSS", "Затронутые версии"]


def test_an_update_row_with_a_figure_the_text_lacks_goes_whole_caveat_and_all() -> None:
    # CODESYS: the article gives the quarter in words. Taking out only the
    # clause with the "4" would leave "Обновление до 3.5.22.40 ...", as if
    # every platform had its fix. The clause with the figure may be the very
    # caveat that the fix is not out, so the row goes whole.
    source = (
        "Разработчик CODESYS GmbH исправляет обе в версиях 3.5.22.40 и 4.23.0.0. "
        "Вторая выйдет только в четвёртом квартале 2026 года."
    )
    claimed = VulnerabilityCard(
        fix="Обновление до 3.5.22.40 для большинства компонентов; "
        "4.23.0.0 для Linux выйдет в 4 квартале 2026 года."
    )

    checked, removed = check_vulnerability(claimed, source)

    assert checked.fix == ""
    assert removed == ["Обновление"]


@pytest.mark.parametrize(
    ("source", "kept"),
    [
        # The model took the version of the standard for the score.
        ("Вектор CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H, оценка не указана.", ""),
        ("Оценка по CVSS v4.0 не приводится.", ""),
        # A real score of 4.0 stays, even next to the version.
        ("Оценка 4.0 по CVSS 3.1: уязвимость средней опасности.", "4.0"),
    ],
)
def test_a_cvss_version_is_no_score(source: str, kept: str) -> None:
    version = "3.1" if "3.1/" in source else "4.0"
    claimed = VulnerabilityCard(cvss_score=kept or version)

    checked, removed = check_vulnerability(claimed, source)

    assert checked.cvss_score == kept
    assert removed == ([] if kept else ["Оценка CVSS"])


def test_an_advisory_number_the_text_gives_is_not_reported_as_removed() -> None:
    # The prompt asks for other ids too. A CISA advisory is not one the card
    # keeps, and the text has it: "not in the text" would be false.
    source = "CISA опубликовала бюллетень ICSA-26-274-03 об уязвимости CVE-2026-1234."
    claimed = VulnerabilityCard(ids=("CVE-2026-1234", "ICSA-26-274-03"))

    _, removed = check_vulnerability(claimed, source)

    assert removed == []


def test_ids_inside_a_run_the_article_gives_by_its_ends_stay_on_the_card() -> None:
    # SCADA «Каскад»: the article gives KWebVision's five BDU entries by the
    # ends of their run, the model writes out each of them.
    source = "Уязвимости KWebVision (BDU:2026-01678–BDU:2026-01682) исправлены в версии 8.3.1."
    run = tuple(f"BDU:2026-{number:05d}" for number in range(1678, 1683))

    checked, _ = check_vulnerability(VulnerabilityCard(ids=(*run, "BDU:2026-01683")), source)

    assert checked.ids == run


def test_a_run_of_thousands_of_ids_is_a_typo_and_names_only_its_ends() -> None:
    claimed = VulnerabilityCard(ids=("CVE-2026-1000", "CVE-2026-5000"))

    checked, _ = check_vulnerability(claimed, "Затронуты CVE-2026-1000–CVE-2026-9000.")

    assert checked.ids == ("CVE-2026-1000",)


def test_an_exploit_the_text_does_not_mention_does_not_raise_the_priority() -> None:
    claimed = VulnerabilityCard(exploit="public", ids=("CVE-2026-1234",))

    checked, removed = check_vulnerability(claimed, "В продукте нашли CVE-2026-1234.")

    assert checked.exploit == "unknown"
    assert "Эксплойт" in removed


def test_an_attack_card_drops_tools_and_indicators_the_text_does_not_name() -> None:
    source = "PhantomCore рассылала фишинговые письма с KermitRAT и HTA-файлами."
    claimed = AttackCard(group="PhantomCore", tools=("KermitRAT", "Cobalt Strike"), iocs=True)

    checked, removed = check_attack(claimed, source)

    assert checked.group == "PhantomCore"
    assert checked.tools == ("KermitRAT",)
    assert checked.iocs is None
    assert removed == ["Инструменты", "Индикаторы компрометации"]


def test_an_attack_card_names_the_vulnerabilities_the_text_does_not() -> None:
    # Both ids in one value: one is the post's, the other the model made up.
    source = "CyberAv3ngers атакует ПЛК Unitronics через CVE-2023-6448."
    claimed = AttackCard(vulnerabilities=("CVE-2023-6448, CVE-2023-12345",))

    checked, removed = check_attack(claimed, source)

    assert checked.vulnerabilities == ("CVE-2023-6448",)
    assert removed == ["CVE-2023-12345"]


class Scripted:
    """A model that gives the answers in turn and keeps the prompts it got."""

    name = "ollama:test"

    def __init__(self, *answers: dict[str, Any]) -> None:
        self.answers = list(answers)
        self.prompts: list[str] = []

    async def ask[T: BaseModel](
        self, schema: type[T], system: str, user: str, tools: Any = ()
    ) -> T:
        self.prompts.append(user)
        self.tools = tools
        return schema.model_validate(self.answers.pop(0))


def _selected(make_article: ArticleFactory, kind: RecordKind, text: str) -> SelectedItem:
    article = make_article("Citrix закрыла уязвимость NetScaler", content=text)
    candidate = Candidate(article=article, interest_id="vuln")
    grade = Grade(relevance=3, interest_id="vuln", kind=kind, by_model=True)
    return SelectedItem(graded=GradedCandidate(candidate=candidate, grade=grade, score=0.9))


async def test_a_figure_the_article_lacks_is_sent_back_once_then_replaced(
    make_article: ArticleFactory, profile: ProfileSpec
) -> None:
    invented = {"headline": "", "summary": "Уязвимой оказалась 41 тысяча устройств.", "why": ""}
    model = Scripted(
        {**invented, "ids": ["CVE-2026-88772"], "exploit": "public"},
        {**invented, "ids": ["CVE-2026-88772"], "exploit": "public"},
    )
    item = _selected(make_article, "vulnerability", BDU_ENTRY)

    written = await ModelIntelligence(cast(Any, model)).summarize(item, profile, None)
    entry = check_entry(written, BDU_ENTRY)

    assert "41" in model.prompts[1]
    assert "нет в публикации" in model.prompts[1]
    assert "41" not in entry.summary
    assert "Пересказ" in entry.unsupported
    assert entry.vulnerability is not None
    assert entry.vulnerability.exploit == "in_the_wild"
    assert priority("vulnerability", entry) == "high"


async def test_management_gets_a_brief_with_tags_and_no_card(
    make_article: ArticleFactory, profile: ProfileSpec
) -> None:
    model = Scripted(
        {
            "headline": "",
            "summary": "Хакеры атаковали электросети. Работа восстановлена.",
            "why": "Нужно проверить подрядчиков.",
            "tags": ["ru", "abroad", "energy"],
        }
    )
    item = _selected(make_article, "attack", "Атака на российские электросети.")
    management = profile.model_copy(update={"audience": "management"})

    written = await ModelIntelligence(cast(Any, model)).summarize(item, management, None)
    entry = check_entry(written, "Атака на российские электросети.")

    assert entry.attack is None
    # Both places at once is a contradiction; the text names Russia.
    assert entry.tags == ("ru", "energy")


def test_markdown_lists_the_card_in_the_datasets_order_and_defangs_post_links(
    digest: Any,  # noqa: F811
) -> None:
    entry = _item(
        7,
        "Citrix закрыла уязвимость",
        kind="vulnerability",
        priority="high",
        priority_reason="эксплойт: используется в атаках",
        vulnerability=VulnerabilityCard(ids=("CVE-2026-88772",), exploit="in_the_wild"),
        unsupported=["Оценка CVSS"],
        links=["https://github.com/x/poc"],
    )
    digest.topics[0].items.append(entry)

    markdown = render_markdown(digest)

    block = markdown[markdown.index("Citrix закрыла уязвимость") :]
    assert "приоритет: высокий (эксплойт: используется в атаках)" in block
    # The card is a table: the label is the first cell of a row.
    labels = [line.split("|")[1].strip() for line in block.splitlines() if line.startswith("| ")]
    assert [label for label in labels if label in {"Уязвимость", "Эксплойт", "CVSS"}] == [
        "Уязвимость",
        "Эксплойт",
        "CVSS",
    ]
    assert "`https://github[.]com/x/poc`" in block
    assert "убрано проверкой: Оценка CVSS" in block


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Wordings from articles the check got wrong before.
        ("Mandiant сообщает об эксплуатации 0-day, CVE-2026-88772, в NetScaler", "in_the_wild"),
        ("Citrix позже подтвердила, что в сети используются две 0-day.", "in_the_wild"),
        ("Cisco Patches Exploited Catalyst SD-WAN Zero-Day Vulnerability", "in_the_wild"),
        ("Эксплойт: существует в открытом доступе. Используется в атаках.", "in_the_wild"),
        ("Исследователи опубликовали PoC.", "public"),
        # Said to be absent: a negation must not read as the thing it denies.
        ("Cisco is not aware of any exploitation in the wild.", "none"),
        ("The flaw has not been exploited in the wild.", "none"),
        ("Уязвимость пока не используется в атаках.", "none"),
        ("Эксплойт: отсутствует.", "none"),
        ("Уязвимость позволяет выполнить код.", "unknown"),
    ],
)
def test_the_exploit_is_read_from_what_the_text_affirms(text: str, expected: str) -> None:
    assert exploit_evidence(text) == expected


def test_in_a_roundup_the_exploit_belongs_to_the_vulnerability_it_is_said_of() -> None:
    roundup = (
        "CVE-2026-1111 в Zimbra уже используется в атаках. "
        "Для CVE-2026-2222 в TeamViewer вышло обновление до 15.82."
    )

    quiet, _ = check_vulnerability(VulnerabilityCard(ids=("CVE-2026-2222",)), roundup)
    exploited, _ = check_vulnerability(VulnerabilityCard(ids=("CVE-2026-1111",)), roundup)

    assert quiet.exploit == "unknown"
    assert exploited.exploit == "in_the_wild"


def test_a_post_link_cannot_close_its_code_span() -> None:
    assert "`" not in defang("https://a.com/x`; [c](http://evil.com)")


async def test_a_year_the_entries_do_not_have_leaves_the_title(
    make_article: ArticleFactory, profile: ProfileSpec
) -> None:
    from radar.domain import Topic

    invented = {"title": "Крупные кибератаки 2024 года", "highlights": ["Атака на ПЛК в 2024 году"]}
    model = Scripted(invented, invented)
    item = _selected(make_article, "attack", "Группировка атаковала ПЛК подстанции.")
    item = item.model_copy(update={"text": ItemSummary(headline="Атака на ПЛК", summary="Атака.")})
    topics = [Topic(title="Атаки на АСУ ТП", items=(item,))]

    overview = await ModelIntelligence(cast(Any, model)).overview(topics, profile)

    assert "2024" in model.prompts[1]
    assert overview.title == "Атаки на АСУ ТП"
    assert overview.highlights == ()


def test_industry_in_the_sectors_counts_as_the_datasets_energy_sector() -> None:
    # PhantomCore's attack on Russian industry is a high-priority example in the dataset.
    card = AttackCard(victim_in_russia=True, sectors="промышленность", energy_sector=False)

    checked, _ = check_attack(card, "PhantomCore атаковала промышленные предприятия РФ.")

    assert priority("attack", ItemSummary(summary="", attack=checked)) == "high"
