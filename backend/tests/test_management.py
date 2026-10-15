"""Management reads less often and in theses: no CVE, versions or hashes,
two sentences an entry, and what the week means for the company first."""

from typing import Any, cast

import pytest

from radar.ai.llm import ModelIntelligence
from radar.cards import plain_brief, plain_lines, technical_tokens
from radar.domain import ItemSummary, ProfileSpec, Topic
from radar.render.markdown import render_markdown
from radar.views import digest_view
from tests.conftest import ArticleFactory
from tests.test_cards import Scripted, _selected
from tests.test_systems import _digest, _entry


@pytest.mark.parametrize(
    "text",
    [
        "Закрыта уязвимость CVE-2026-1234.",
        "Запись BDU:2026-01234 опубликована.",
        "Оценка CVSS 9.8 по шкале.",
        "Опубликованы IoC атаки.",
        "Хеш e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 найден.",
        "Сервер 185.12.4.7 управлял ботами.",
        "Обновите до версии 5.4.2.",
        "SCADA-система «Каскад» версии 8.3 уязвима.",
        "Уязвимости оценены от 6,9 до 9,3 баллов.",
    ],
)
def test_technical_details_are_found(text: str) -> None:
    assert technical_tokens(text)


@pytest.mark.parametrize(
    "text",
    [
        "Атака случилась 01.10.2026.",
        "В Android 15.1 закрыта ошибка.",
        "Итоги 2026 года.",
        "ФСТЭК выпустила требования.",
        "Минцифры вынесло Антифрод 3.0 на обсуждение.",
        "Атаки достигают нагрузки до 3,5 Тбит/с.",
    ],
)
def test_dates_years_and_plain_words_are_not_technical(text: str) -> None:
    assert technical_tokens(text) == []


def test_a_brief_keeps_two_sentences() -> None:
    text = ItemSummary(summary="Первое событие. Второе следствие. Третье лишнее.")

    assert plain_brief(text).summary == "Первое событие. Второе следствие."


def test_a_sentence_with_a_cve_leaves_the_brief() -> None:
    text = ItemSummary(
        summary="Хакеры атаковали подрядчика. Использована уязвимость CVE-2026-1234. "
        "Пострадали поставки."
    )

    assert plain_brief(text).summary == "Хакеры атаковали подрядчика. Пострадали поставки."


def test_a_brief_all_about_a_cve_keeps_one_sentence_without_it() -> None:
    text = ItemSummary(summary="Microsoft закрыла уязвимость CVE-2026-1234 в Windows.")

    assert plain_brief(text).summary == "Microsoft закрыла уязвимость в Windows."


def test_a_version_of_two_numbers_leaves_a_brief_when_the_text_calls_it_a_version() -> None:
    # As management read it on 03.10: the retelling kept "версии 8.3".
    text = ItemSummary(
        summary="Эксперты Positive Technologies нашли 17 уязвимостей в компонентах "
        "SCADA-системы «Каскад» версии 8.3, которые могли позволить злоумышленнику "
        "управлять технологическими процессами; разработчик выпустил патч-обновление 8.3.1."
    )

    assert plain_brief(text).summary == (
        "Эксперты Positive Technologies нашли 17 уязвимостей в компонентах "
        "SCADA-системы «Каскад», которые могли позволить злоумышленнику "
        "управлять технологическими процессами; разработчик выпустил патч-обновление."
    )


def test_a_score_leaves_with_the_word_cvss() -> None:
    text = ItemSummary(summary="Уязвимости оценивались по шкале CVSS 4.0 от 6,9 до 9,3 баллов.")

    assert plain_brief(text).summary == "Уязвимости оценивались по шкале."


def test_a_headline_loses_its_ids_and_the_brackets_they_stood_in() -> None:
    text = ItemSummary(
        headline="Citrix NetScaler: две 0-day уязвимости (CVE-2026-88771 и CVE-2026-88772) "
        "позволяют удалённое выполнение кода и DoS",
        summary="Атака.",
    )

    assert plain_brief(text).headline == (
        "Citrix NetScaler: две 0-day уязвимости позволяют удалённое выполнение кода и DoS"
    )


def test_why_with_an_address_is_dropped() -> None:
    text = ItemSummary(summary="Атака на банк.", why="Заблокируйте адрес 185.12.4.7.")

    assert plain_brief(text).why == ""


def test_a_thesis_is_one_line_without_technical_details() -> None:
    lines = [
        "Атаки на подрядчиков энергетики выросли. Это второе предложение.",
        "Уязвимость CVE-2026-1234 используется в атаках.",
        "Регулятор ужесточил требования к КИИ.",
    ]

    assert plain_lines(lines, 5) == (
        "Атаки на подрядчиков энергетики выросли.",
        "Регулятор ужесточил требования к КИИ.",
    )


def test_a_long_thesis_is_cut_at_a_word() -> None:
    line = "Слово " * 40

    (cut,) = plain_lines([line], 5)

    assert len(cut) <= 160
    assert cut.endswith("…")
    assert not cut[:-1].endswith(" ")


async def test_a_brief_with_technical_details_goes_back_once(
    make_article: ArticleFactory, profile: ProfileSpec
) -> None:
    technical = {
        "headline": "Взлом подрядчика",
        "summary": "Злоумышленники использовали CVE-2026-1234 в версии 5.4.2.",
        "why": "",
        "tags": ["abroad"],
    }
    plain = {**technical, "summary": "Злоумышленники проникли к подрядчику через старую ошибку."}
    model = Scripted(technical, plain)
    item = _selected(make_article, "attack", "Злоумышленники использовали CVE-2026-1234 в 5.4.2.")
    management = profile.model_copy(update={"audience": "management"})

    written = await ModelIntelligence(cast(Any, model)).summarize(item, management, None)

    assert len(model.prompts) == 2
    assert "CVE-2026-1234" in model.prompts[1]
    assert "без технических деталей" in model.prompts[1]
    assert written.summary == plain["summary"]


async def test_management_gets_what_the_period_means_for_the_company(
    make_article: ArticleFactory, profile: ProfileSpec
) -> None:
    answer = {
        "title": "Атаки на подрядчиков",
        "highlights": ["Подрядчики стали главным входом.", "Ошибка CVE-2026-1234 опасна."],
        "implications": ["Проверить доступы подрядчиков.", "Обновить план реагирования."],
    }
    # The CVE's figures are in no entry: the answer goes back once and stays the same.
    model = Scripted(answer, answer)
    item = _selected(make_article, "attack", "Подрядчик взломан.")
    item = item.model_copy(update={"text": ItemSummary(headline="Взлом", summary="Взлом.")})
    management = profile.model_copy(update={"audience": "management"})

    overview = await ModelIntelligence(cast(Any, model)).overview(
        [Topic(title="Подрядчики", items=(item,))], management
    )

    assert overview.highlights == ("Подрядчики стали главным входом.",)
    assert overview.implications == (
        "Проверить доступы подрядчиков.",
        "Обновить план реагирования.",
    )


@pytest.mark.parametrize("audience", ["specialist", "management"])
def test_the_sources_own_titles_name_no_ids_to_management(audience: str) -> None:
    post = _entry(1, "Mandiant: злоумышленники используют уязвимость Citrix NetScaler", 0, {})
    post.article.title = (
        "Mandiant сообщает об эксплуатации 0-day, CVE-2026-88772, в Citrix NetScaler, "
        "связанной с развертыванием веб-оболочек"
    )
    left_out = _entry(
        2, "Критическая уязвимость обхода аутентификации в WSO2 API Manager (CVE-2026-5430)", 0, {}
    )
    left_out.selected = False
    left_out.topic_id = None
    left_out.headline = ""
    digest = _digest((), [post, left_out])
    digest.profile_spec = {**digest.profile_spec, "audience": audience}

    markdown = render_markdown(digest_view(digest))

    if audience == "specialist":
        assert "CVE-2026-88772" in markdown
        assert "CVE-2026-5430" in markdown
        return
    assert "CVE" not in markdown
    assert (
        "Оригинал: Mandiant сообщает об эксплуатации 0-day, в Citrix NetScaler, "
        "связанной с развертыванием веб-оболочек"
    ) in markdown
    assert "Критическая уязвимость обхода аутентификации в WSO2 API Manager]" in markdown


def test_an_issue_saved_before_the_rules_reads_to_management_without_them() -> None:
    # The entry as management's issue of 03.10 saved it, before the rules.
    entry = _entry(
        1, "Positive Technologies помогла исправить 17 уязвимостей в SCADA-системе", 0, {}
    )
    entry.summary = (
        "Эксперты Positive Technologies нашли 17 уязвимостей в компонентах SCADA-системы "
        "«Каскад» версии 8.3, которые могли позволить злоумышленнику управлять "
        "технологическими процессами; разработчик выпустил патч-обновление 8.3.1."
    )
    entry.why = (
        "Необходимо установить обновление версии 8.3.1 и ограничить доступ к компонентам "
        "SCADA из внешних и корпоративных сетей, используя межсетевые экраны и мониторинг трафика."
    )
    entry.reason = "Критическая уязвимость CVE-2026-88771 в SCADA"
    digest = _digest((), [entry])
    digest.profile_spec = {**digest.profile_spec, "audience": "management"}
    digest.title = "Cisco Catalyst SD-WAN Manager: критическая уязвимость CVE-2026-76504"
    digest.highlights = ["Закрыта уязвимость CVE-2026-76504.", "Атаки на энергетику растут."]
    digest.topics[0].title = "Citrix NetScaler: уязвимости CVE-2026-88771 и CVE-2026-88772"
    digest.topics[0].overview = "Уязвимость оценена в 9,8 балла. Атакуют подрядчиков."

    view = digest_view(digest)

    assert view.title == "Cisco Catalyst SD-WAN Manager: критическая уязвимость"
    assert view.highlights == ["Атаки на энергетику растут."]
    assert view.topics[0].title == "Citrix NetScaler: уязвимости"
    assert view.topics[0].overview == "Атакуют подрядчиков."
    item = view.topics[0].items[0]
    assert item.summary == (
        "Эксперты Positive Technologies нашли 17 уязвимостей в компонентах SCADA-системы "
        "«Каскад», которые могли позволить злоумышленнику управлять "
        "технологическими процессами; разработчик выпустил патч-обновление."
    )
    assert item.why == ""
    assert item.reason == "Критическая уязвимость в SCADA"
