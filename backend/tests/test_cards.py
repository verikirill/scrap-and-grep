"""The organizers' dataset: record kinds, priorities, cards and their check."""

from typing import Any, cast

import pytest
from pydantic import BaseModel

from radar.ai.llm import ModelIntelligence
from radar.cards import (
    attack_rows,
    check_attack,
    check_entry,
    check_vulnerability,
    defang,
    exploit_evidence,
    indicators,
    priority,
    technical_marks,
    without_marks,
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
    assert removed == ["Идентификаторы", "Оценка CVSS", "Затронутые версии"]


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


def test_an_attack_card_takes_the_indicators_and_techniques_the_article_prints() -> None:
    source = (
        "Группа использовала DCOM для перемещения (T1021.003) и T1190; "
        "модель T1000 тут ни при чём. "
        "Индикаторы: 44D88612FEA8A8F36DE82E1278ABB02F, C2 evil[.]com и 192.168.10[.]5, "
        "загрузка с hxxps://bad[.]site/p.php. Затронута версия 20.9.10.1."
    )

    checked, removed = check_attack(AttackCard(iocs=None), source)

    assert checked.indicators == (
        "44d88612fea8a8f36de82e1278abb02f",
        "evil[.]com",
        "192.168.10[.]5",
        "hxxps://bad[.]site/p.php",
    )
    assert checked.iocs is True
    assert checked.techniques == (
        "T1021.003 Distributed Component Object Model",
        "T1190 Exploit Public-Facing Application",
    )
    assert removed == []
    rows = dict(attack_rows(checked))
    assert rows["Индикаторы компрометации"].startswith("44d88612fea8a8f36de82e1278abb02f, evil")
    assert rows["Техники MITRE ATT&CK"].startswith("T1021.003 Distributed Component Object Model")


def test_a_card_without_techniques_shows_no_empty_attack_row() -> None:
    labels = [label for label, _ in attack_rows(AttackCard(iocs=False))]

    assert "Техники MITRE ATT&CK" not in labels
    assert dict(attack_rows(AttackCard(iocs=False)))["Индикаторы компрометации"] == "нет"


def test_a_dotted_version_is_not_an_indicator() -> None:
    assert indicators("Обновите до 20.9.10.1 или 7.18.1; адрес 10.0.0.1 в тексте без защиты") == ()


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
    labels = [line.split(":**")[0].removeprefix("- **") for line in block.splitlines()]
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


async def test_a_management_brief_with_technical_marks_goes_back_then_is_cut(
    make_article: ArticleFactory, profile: ProfileSpec
) -> None:
    technical = {
        "headline": "Уязвимость CVE-2026-88772 в NetScaler",
        "summary": "Citrix закрыла уязвимость. Оценка CVSS 9. Атакующие уже её используют.",
        "why": "Обновите шлюзы до 14.1-47.48.",
        "tags": ["abroad"],
    }
    model = Scripted(technical, technical)
    item = _selected(make_article, "vulnerability", BDU_ENTRY)
    management = profile.model_copy(update={"audience": "management"})

    entry = await ModelIntelligence(cast(Any, model)).summarize(item, management, None)

    # Sent back once with what is wrong, then cut by hand.
    assert "CVE-2026-88772" in model.prompts[1]
    assert "одного-двух предложений" in model.prompts[1]
    assert entry.summary == "Citrix закрыла уязвимость. Атакующие уже её используют."
    assert technical_marks(f"{entry.headline} {entry.summary} {entry.why}") == set()


async def test_management_overview_says_what_it_means_for_the_company(
    make_article: ArticleFactory, profile: ProfileSpec
) -> None:
    from radar.domain import Topic

    answer = {
        "title": "Атаки на энергетику",
        "highlights": [
            "Группировка атаковала подстанции.",
            "Оценка CVSS у уязвимости критическая.",
        ],
        "implications": ["Стоит проверить удалённый доступ подрядчиков к АСУ ТП."],
    }
    model = Scripted(answer)
    item = _selected(make_article, "attack", "Группировка атаковала подстанции.")
    item = item.model_copy(update={"text": ItemSummary(headline="Атака", summary="Атака.")})
    management = profile.model_copy(update={"audience": "management"})

    overview = await ModelIntelligence(cast(Any, model)).overview(
        [Topic(title="Атаки", items=(item,))], management
    )

    assert overview.implications == ("Стоит проверить удалённый доступ подрядчиков к АСУ ТП.",)
    # A key point with an identifier is no key point for management.
    assert overview.highlights == ("Группировка атаковала подстанции.",)


def test_technical_marks_are_identifiers_scores_addresses_and_hashes() -> None:
    text = (
        "CVE-2026-1111, BDU:2026-01234, CVSS 9.8, IoC 10.0.0.1 и "
        "d41d8cd98f00b204e9800998ecf8427e, но не 187-ФЗ и не версия 2.0"
    )

    assert technical_marks(text) == {
        "CVE-2026-1111",
        "BDU:2026-01234",
        "CVSS",
        "IoC",
        "10.0.0.1",
        "d41d8cd98f00b204e9800998ecf8427e",
    }
    assert without_marks("Уязвимость CVE-2026-88772 в NetScaler") == "Уязвимость в NetScaler"
