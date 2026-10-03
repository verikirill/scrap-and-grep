"""The reader's own systems: which entries name them, how such an entry is
marked and where it stands in its topic."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from radar.db.models import Article, Digest, DigestItem, DigestTopic, Source
from radar.domain import Interest, ProfileSpec
from radar.render.markdown import item_meta
from radar.systems import affected_systems
from radar.views import ItemView, digest_view

PUBLISHED = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)


def test_a_system_the_text_names_is_found() -> None:
    text = "Обход аутентификации в Cisco ASA и FTD"

    assert affected_systems(("Cisco ASA",), text) == ("Cisco ASA",)


def test_every_word_of_a_system_has_to_be_in_the_text() -> None:
    text = "Критическая уязвимость в Cisco Catalyst SD-WAN Manager"

    assert affected_systems(("Cisco ASA",), text) == ()


def test_a_word_inside_a_longer_one_does_not_count() -> None:
    assert affected_systems(("ABB",), "Abbott сообщила о взломе") == ()
    assert affected_systems(("ABB",), "ABB PCM600 ≤ 2.14: повышение привилегий") == ("ABB",)


def test_a_model_number_is_split_on_punctuation_and_compared_whole() -> None:
    systems = ("Siemens S7-1500",)

    assert affected_systems(systems, "Siemens SIMATIC S7-1500: отказ в обслуживании") == systems
    assert affected_systems(systems, "Siemens SIMATIC S7-1200: отказ в обслуживании") == ()


def test_cyrillic_is_compared_without_case() -> None:
    text = "Обновление КРИПТОПРО csp закрывает уязвимость"

    assert affected_systems(("КриптоПро CSP",), text) == ("КриптоПро CSP",)


def test_yo_and_ye_are_one_letter() -> None:
    assert affected_systems(("Расчёт-Энерго",), "Взлом «Расчет Энерго»") == ("Расчёт-Энерго",)
    assert affected_systems(("Расчет Энерго",), "Взлом «Расчёт-Энерго»") == ("Расчет Энерго",)


def test_one_c_is_found_in_either_alphabet() -> None:
    # The system with a Cyrillic С, the text with a Latin C, and the other way.
    assert affected_systems(("1С",), "Уязвимость в 1C:Предприятие 8.3") == ("1С",)
    assert affected_systems(("1C",), "Обновление 1С-Битрикс") == ("1C",)


def test_one_c_is_not_a_digit_and_a_letter_apart() -> None:
    assert affected_systems(("1С",), "С 1 октября вступают в силу требования") == ()
    assert affected_systems(("1С",), "контроллер серии 11С") == ()


def test_a_system_without_a_word_of_two_characters_matches_nothing() -> None:
    assert affected_systems(("R", "-"), "R и - в тексте") == ()


def test_the_systems_come_in_the_order_of_the_profile() -> None:
    systems = ("Fortinet", "Cisco", "Siemens")

    assert affected_systems(systems, "Cisco и Fortinet выпустили патчи") == ("Fortinet", "Cisco")


def _profile(**extra: Any) -> ProfileSpec:
    return ProfileSpec(name="ИБ АСУ ТП", interests=(Interest(id="ics", title="АСУ ТП"),), **extra)


def test_the_profile_cleans_its_list_of_systems() -> None:
    profile = _profile(systems=["  Cisco ASA ", "", "   ", "cisco asa", "1С", "x" * 100])

    assert profile.systems == ("Cisco ASA", "1С", "x" * 80)


def test_the_systems_leave_the_cache_of_the_model_alone() -> None:
    base = _profile()

    assert _profile(systems=("Cisco ASA", "1С")).fingerprint() == base.fingerprint()
    # The control: what the model does read changes it.
    assert _profile(exclusions=("вакансии",)).fingerprint() != base.fingerprint()


SOURCE = Source(name="SecurityLab", category="security", fetch_method=None, fetch_via_proxy=False)


def _entry(article_id: int, headline: str, topic_id: int, card: dict[str, Any]) -> DigestItem:
    article = Article(
        id=article_id,
        url=f"https://example.org/{article_id}",
        title=headline,
        language="ru",
        published_at=PUBLISHED,
        word_count=None,
        links=[],
    )
    article.source = SOURCE
    return DigestItem(
        article=article,
        article_id=article_id,
        topic_id=topic_id,
        selected=True,
        score=0.8,
        retrieval_score=0.7,
        personal=0.0,
        personal_note="",
        relevance=2,
        interest_id="ics",
        reason="",
        reject_reason=None,
        headline=headline,
        summary="",
        why="",
        duplicates=[],
        kind="news",
        priority=None,
        card=card,
    )


def _digest(systems: tuple[str, ...], *topics: list[DigestItem]) -> Digest:
    digest = Digest(
        id=uuid.UUID(int=1),
        profile_id=None,
        profile_spec=_profile(systems=systems).model_dump(mode="json"),
        profile_version=1,
        period_start=PUBLISHED,
        period_end=PUBLISHED,
        status="done",
        stage="done",
        progress=1.0,
        error=None,
        title="Выпуск",
        highlights=[],
        implications=[],
        stats={},
        origin="manual",
        created_at=PUBLISHED,
        finished_at=PUBLISHED,
    )
    digest.topics = [
        DigestTopic(id=index, position=index, title=f"Тема {index}", overview="")
        for index in range(len(topics))
    ]
    digest.items = [item for items in topics for item in items]
    return digest


@pytest.mark.parametrize(
    ("systems", "card"),
    [
        pytest.param(
            ("Cisco ASA",),
            {"vulnerability": {"name": "Обход аутентификации в Cisco ASA"}},
            id="vulnerability.name",
        ),
        pytest.param(
            ("Cisco ASA",),
            {"vulnerability": {"affected": "Cisco ASA 9.16-9.20"}},
            id="vulnerability.affected",
        ),
        pytest.param(
            ("ABB PCM600",),
            {"vulnerability": {"equipment": "ABB PCM600 версии 2.14"}},
            id="vulnerability.equipment",
        ),
        pytest.param(
            ("AnyDesk",),
            {"attack": {"tools": ["Mimikatz", "AnyDesk"]}},
            id="attack.tools",
        ),
        pytest.param(
            ("Siemens SIMATIC",),
            {"attack": {"sectors": "промышленность, системы на Siemens SIMATIC"}},
            id="attack.sectors",
        ),
        pytest.param(
            ("Cisco ASA",),
            {"attack": {"affected": "межсетевые экраны Cisco ASA"}},
            id="attack.affected",
        ),
    ],
)
def test_an_entry_is_marked_by_what_its_card_names(
    systems: tuple[str, ...], card: dict[str, Any]
) -> None:
    entry = _entry(1, "Новая кампания против промышленности", 0, card)

    view = digest_view(_digest(systems, [entry]))

    assert view.topics[0].items[0].ours == list(systems)


def test_an_entry_is_marked_by_its_headline_and_not_by_a_system_it_omits() -> None:
    entries = [
        _entry(1, "Fortinet закрыла уязвимость в FortiMail", 0, {}),
        _entry(2, "Шифровальщик атаковал электросети", 0, {}),
    ]

    items = digest_view(_digest(("Cisco", "Fortinet"), entries)).topics[0].items

    assert [item.ours for item in items] == [["Fortinet"], []]


def test_our_entries_go_first_in_their_topic_and_keep_their_order() -> None:
    first = [
        _entry(1, "Шифровальщик атаковал электросети", 0, {}),
        _entry(2, "Cisco ASA: обход аутентификации", 0, {}),
        _entry(3, "ФСТЭК обновила требования", 0, {}),
        _entry(4, "CODESYS: две уязвимости", 0, {}),
    ]
    second = [
        _entry(5, "Утечка данных у ритейлера", 1, {}),
        _entry(6, "Fortinet: активная эксплуатация", 1, {}),
    ]

    view = digest_view(_digest(("CODESYS", "Cisco ASA", "Fortinet"), first, second))

    assert [item.article_id for item in view.topics[0].items] == [2, 4, 1, 3]
    assert [item.article_id for item in view.topics[1].items] == [6, 5]


def _view(**extra: Any) -> ItemView:
    return ItemView.model_validate(
        {
            "article_id": 1,
            "url": "https://example.org/1",
            "title": "Cisco ASA",
            "headline": "Cisco ASA",
            "source_name": "SecurityLab",
            "source_category": "security",
            "language": "ru",
            "published_at": PUBLISHED,
            "score": 0.82,
            "retrieval_score": 0.7,
            "relevance": 2,
            "interest_id": None,
            "interest_title": None,
            "reason": "",
            "summary": "",
            "why": "",
            **extra,
        }
    )


def test_the_line_under_the_headline_says_which_of_our_systems_it_concerns() -> None:
    meta = item_meta(_view(ours=["Cisco ASA", "Siemens S7-1500"]))

    assert meta[:2] == ["SecurityLab", "касается нас: Cisco ASA, Siemens S7-1500"]
    assert not any(part.startswith("касается нас") for part in item_meta(_view()))
