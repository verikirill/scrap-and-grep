"""Management reads less often and in theses: no CVE, versions or hashes,
two sentences an entry, and what the week means for the company first."""

from typing import Any, cast

import pytest

from radar.ai.llm import ModelIntelligence
from radar.cards import plain_brief, plain_lines, technical_tokens
from radar.domain import ItemSummary, ProfileSpec, Topic
from tests.conftest import ArticleFactory
from tests.test_cards import Scripted, _selected


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
