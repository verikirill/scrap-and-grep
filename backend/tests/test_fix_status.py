"""The update row and the advice of a vulnerability entry agree on whether the
fix is out. The sentences are from the week of the examples (data/samples)."""

import pytest

from radar.domain import ItemSummary, VulnerabilityCard, VulnerabilityReference
from radar.fix_status import (
    ADVICE_REPLACED,
    PARTIAL_NOTE,
    advises_patch,
    fix_status,
    pending_advice,
    reconcile_fix,
    row_says_pending,
)

# t.me/true_secator/8672, 2 October.
FORTIMAIL_POST = (
    "Пользователи FortiMail 7.2 могут устранить уязвимость, обновив систему до ветки 7.4 или "
    "более поздней версии. Для затронутых установок FortiMail 7.4, 7.6 и 8.0 обновления пока "
    "недоступны. FortiMail 7.4.9, 7.6.7 и 8.0.2 указаны в качестве предстоящих версий, "
    "содержащих исправление."
)
# 1275.ru, the same day: says it without naming the CVE in the sentence.
FORTIMAIL_1275 = (
    "Уязвимость CVE-2026-104286 в почтовом шлюзе Fortinet FortiMail. Исправления на момент "
    "публикации ещё готовятся: Fortinet называет версии 8.0.2, 7.6.7 и 7.4.9. Пока обновлений "
    "нет, вендор советует отключить поддержку IBE."
)
# BleepingComputer, 1 October.
FORTIMAIL_ENGLISH = (
    "For affected FortiMail 7.4, 7.6, and 8.0 installations, security updates are not yet "
    "available, with Fortinet listing FortiMail 7.4.9, 7.6.7, and 8.0.2 as upcoming versions."
)
# 1275.ru on CODESYS: one branch fixed, another in the fourth quarter.
CODESYS = (
    "Разработчик CODESYS GmbH исправляет обе в версиях 3.5.22.40 и 4.23.0.0. Вторая выйдет "
    "только в четвёртом квартале 2026 года. Скачать исправления можно установщиком CODESYS. "
    "Пока версия 4.23.0.0 не вышла, устройства на Linux остаются уязвимыми."
)
CISCO = "Cisco выпустила обновления для устранения критической 0-day в Catalyst SD-WAN Manager."


def _entry(fix: str = "", workaround: str = "", why: str = "") -> ItemSummary:
    return ItemSummary(
        summary="Уязвимость позволяет записывать произвольные файлы.",
        why=why,
        vulnerability=VulnerabilityCard(
            ids=("CVE-2026-104286",), fix=fix, workaround=workaround, exploit="in_the_wild"
        ),
    )


@pytest.mark.parametrize("article", [FORTIMAIL_1275, FORTIMAIL_ENGLISH])
def test_an_update_the_article_calls_coming_is_not_out(article: str) -> None:
    card = VulnerabilityCard(ids=("CVE-2026-104286",), fix="Обновить до 7.4.9")

    assert fix_status(card, article) == "pending"


@pytest.mark.parametrize(
    "article",
    [
        # How the articles of the snapshot said it.
        "Для затронутых установок FortiMail 7.4, 7.6 и 8.0 обновления пока недоступны.",
        "Пока не появятся исправленные версии, Fortinet предлагает отключить поддержку IBE.",
        'Fortinet lists fixes for several affected branches as "upcoming," leaving customers '
        "reliant on workarounds.",
        "Вторая выйдет только в четвёртом квартале 2026 года.",
        "Платформы для Linux и встраиваемых систем ждут релиза 4.23.0.0.",
        "Пока версия 4.23.0.0 не вышла, устройства на Linux остаются уязвимыми.",
        "Пока обновлений нет, вендор советует отключить поддержку IBE.",
        "Пока исправления нет, ABB предлагает обходные меры.",
        "Готовых обновлений на дату публикации нет: все исправленные версии вендор помечает как "
        "предстоящие.",
        "Исправления вендор обещает в версиях 8.0.2, 7.6.7 и 7.4.9.",
        "Until patched versions are available, Fortinet says admins can mitigate the flaw.",
        "Monta версий с исправлениями пока не выпустила.",
        # And as English news usually puts it.
        "Patches have not yet been released.",
        "The vendor has yet to release a fix.",
    ],
)
def test_the_ways_to_say_a_fix_is_coming_read_as_not_out(article: str) -> None:
    assert fix_status(VulnerabilityCard(), article) == "pending"


@pytest.mark.parametrize(
    "article",
    [
        "Обновления доступны для всех поддерживаемых версий.",
        "Исправление выпущено в версии 2.4.1.",
        "A patch is available in version 7.4.9.",
        "The flaw is fixed in version 3.2.1.",
        "It released fixes for both, along with six other flaws.",
        # What is missing is said of the readers, the details or an exploit.
        "Обновления доступны с августа, однако тысячи серверов ещё не обновлены.",
        "Патч выпущен, но пока не все пользователи его установили.",
        "Исправление уже выпущено, пока публичный эксплойт не появился.",
        "Cisco released patches but has not released details about the attacks.",
        "Fixes are available in version 7.4.9; upcoming releases will add hardening.",
        "CISA recommends mitigations until patches can be installed.",
        # Attacks before a release that came since (the snapshot's ZeroDay Alert).
        "Уязвимости в Citrix NetScaler эксплуатировались несколько недель до выхода исправлений.",
        "Если эксплуатация началась до выхода патча, уязвимость относится к нулевому дню.",
        # A denial of service leaves a device "недоступным"; firmware is the
        # product, not its fix.
        "Уязвимость в прошивке контроллеров позволяет сделать их недоступными.",
        "Обновление устраняет уязвимость, из-за которой сервер становится недоступным.",
        "Версия 4.2 с исправлением вышла 30 сентября, обновление обещает закрыть все три бреши.",
        # The fix is not what is missing or awaited: a virtual patch is a rule of
        # a filter (1275 on FortiMail: "Виртуального патча нет"), a reboot comes
        # after an update, a forged update is the attack itself.
        "Исправление вышло 1 октября, но виртуального патча нет: WAF атаку не остановит.",
        "После установки обновления ожидается перезагрузка контроллера.",
        "Поддельное обновление прошивки делает контроллер недоступным.",
    ],
)
def test_a_fix_that_is_out_is_not_read_as_coming(article: str) -> None:
    assert fix_status(VulnerabilityCard(), article) == ""


@pytest.mark.parametrize(
    ("row", "pending"),
    [
        ("Обновление до FortiMail 7.4.9, 7.6.7 или 8.0.2 (пока недоступно, ожидается).", True),
        (
            "Обновить до версии выше 2.14, если доступно обновление от ABB; в текущем выпуске "
            "исправления нет.",
            True,
        ),
        ("Обновить до FortiMail 7.4.9, 7.6.7 или 8.0.2, когда они станут доступны.", True),
        # The two shapes the card prompt asks for.
        ("Ещё не выпущено, ожидается версия 4.23.0.0.", True),
        ("Выпущено, версия 3.5.22.40.", False),
        # Knowing nothing is not knowing that the fix is coming; "if available" hedges.
        ("Пока нет данных.", False),
        ("Обновить до последней версии, если доступно обновление.", False),
        (
            "Citrix выпустила исправления для обеих уязвимостей; обновиться до последних версий.",
            False,
        ),
    ],
)
def test_the_update_row_says_the_fix_is_coming_only_in_so_many_words(
    row: str, pending: bool
) -> None:
    assert row_says_pending(row) is pending


def test_one_branch_fixed_and_another_coming_is_a_partial_fix() -> None:
    assert fix_status(VulnerabilityCard(), CODESYS) == "partial"
    # The post says 7.2 may move to 7.4, and 7.4 itself waits for 7.4.9.
    assert fix_status(VulnerabilityCard(), FORTIMAIL_POST) == "pending"


def test_a_released_update_leaves_the_entry_as_written() -> None:
    entry = _entry(fix="Обновить до версии из бюллетеня Cisco", why="Установите патч сегодня.")

    assert fix_status(entry.vulnerability or VulnerabilityCard(), CISCO) == ""
    assert reconcile_fix(entry, CISCO) == entry


def test_advice_to_install_a_patch_that_is_not_out_gives_way_to_the_workaround() -> None:
    """examples/change/02-exclusion/after.md:83, the jury's FortiMail entry."""
    entry = _entry(
        fix="Обновление до FortiMail 7.4.9, 7.6.7 или 8.0.2 (пока недоступно для текущих веток).",
        workaround=(
            "Отключить функцию IBE; ограничить доступ к веб-интерфейсу FortiMail из Интернета."
        ),
        why="Необходимо срочно применить обходные меры и установить патч, иначе подстанции "
        "могут быть скомпрометированы через FortiMail.",
    )

    fixed = reconcile_fix(entry, FORTIMAIL_POST)

    assert fixed.why == (
        "Исправление ещё не выпущено, до его выхода: отключить функцию IBE; ограничить доступ "
        "к веб-интерфейсу FortiMail из Интернета."
    )
    assert not advises_patch(fixed.why)
    assert fixed.vulnerability is not None
    # The row said it already: it stays word for word.
    assert fixed.vulnerability.fix == entry.vulnerability.fix  # type: ignore[union-attr]
    assert ADVICE_REPLACED in fixed.unsupported


def test_an_update_row_that_hides_the_wait_gets_it_stated() -> None:
    """examples/change/02-exclusion/after.md:135: the row read as if 8.0.2 were out.
    The note is a sentence of its own: in brackets it read as said of the move
    from 7.2 to 7.4, which is out."""
    entry = _entry(
        fix="Обновить до FortiMail 8.0.2, 7.6.7 или 7.4.9; для ветки 7.2 рекомендуется перейти "
        "на 7.4 или новее.",
        why="Необходимо проверить доступность веб-консоли FortiMail из интернета и установить "
        "патч, иначе система может быть скомпрометирована.",
    )

    fixed = reconcile_fix(entry, FORTIMAIL_1275)

    assert fixed.vulnerability is not None
    assert fixed.vulnerability.fix == (
        "Обновить до FortiMail 8.0.2, 7.6.7 или 7.4.9; для ветки 7.2 рекомендуется перейти "
        "на 7.4 или новее. Исправление ещё не выпущено."
    )
    assert (
        fixed.why == "Исправление ещё не выпущено: следите за выходом обновления у производителя."
    )


@pytest.mark.parametrize(
    ("fix", "article", "expected"),
    [
        (
            "Выпущено, версии 8.0.2, 7.6.7 и 7.4.9.",
            FORTIMAIL_1275,
            "Ещё не выпущено: версии 8.0.2, 7.6.7 и 7.4.9.",
        ),
        ("Выпущено.", FORTIMAIL_1275, "Исправление ещё не выпущено."),
        # One branch is out: "выпущено" is true of it, the caveat covers the rest.
        (
            "Выпущено, версия 3.5.22.40.",
            CODESYS,
            "Выпущено, версия 3.5.22.40. Для части версий исправление ещё не выпущено.",
        ),
    ],
)
def test_an_update_row_that_calls_a_coming_fix_released_is_put_right(
    fix: str, article: str, expected: str
) -> None:
    """The card prompt asks for "выпущено, версия ..." or "ещё не выпущено,
    ожидается ...": the note after "Выпущено" would contradict the row."""
    fixed = reconcile_fix(_entry(fix=fix), article)

    assert fixed.vulnerability is not None
    assert fixed.vulnerability.fix == expected


@pytest.mark.parametrize(
    ("why", "advice"),
    [
        ("Необходимо срочно применить обходные меры и установить патч.", True),
        # A condition other than the release does not make the advice wait for it.
        ("Если интерфейс доступен из интернета, срочно установите патч.", True),
        ("Установите патч и запланируйте проверку журналов.", True),
        # Worded as a need, as in examples/models/*/ics-security-engineer.md.
        ("Для инженера это означает необходимость немедленного обновления контроллеров.", True),
        ("Критические уязвимости требуют немедленного обновления до указанных версий.", True),
        # A version said to be installed is no advice to install one.
        (
            "Если на подстанциях установлена уязвимая версия FortiMail, нарушитель получит доступ.",
            False,
        ),
        # Advice tied to the release agrees with a fix that is not out.
        ("Ограничьте доступ к интерфейсу до установки обновлений.", False),
        ("Установите обновление после выхода исправленных версий.", False),
        ("Примените временные меры и планируйте обновление.", False),
        ("Подготовьтесь к установке патча, как только он появится.", False),
        ("Примените патч, если он доступен.", False),
    ],
)
def test_advice_to_patch_now_is_told_from_advice_tied_to_the_release(
    why: str, advice: bool
) -> None:
    assert advises_patch(why) is advice


def test_a_workaround_that_opens_with_a_vendors_name_keeps_its_capital() -> None:
    """examples/custom-sources/specialist-3d-20261004-1746.md:42."""
    entry = _entry(
        fix="Обновление до FortiMail 7.4.9 (пока недоступно).",
        workaround="Fortinet предоставил временный обход; детали следует получить у поставщика.",
        why="Установите патч.",
    )

    assert reconcile_fix(entry, FORTIMAIL_POST).why == (
        "Исправление ещё не выпущено, до его выхода: Fortinet предоставил временный обход; "
        "детали следует получить у поставщика."
    )


@pytest.mark.parametrize("workaround", ["Нет указанных временных мер защиты.", "N/A"])
def test_a_workaround_row_that_names_none_leaves_the_reader_to_watch_the_vendor(
    workaround: str,
) -> None:
    """Rows the models wrote in examples/models/*/ics-security-engineer.md."""
    entry = _entry(
        fix="Обновление до FortiMail 7.4.9 (пока недоступно).",
        workaround=workaround,
        why="Установите патч.",
    )

    assert reconcile_fix(entry, FORTIMAIL_POST).why == (
        "Исправление ещё не выпущено: следите за выходом обновления у производителя."
    )


def test_advice_tied_to_the_release_is_left_as_it_is() -> None:
    """examples/it-infrastructure-lead.md:58 got it right."""
    why = (
        "Необходимо немедленно ограничить доступ к интерфейсу управления FortiMail и применить "
        "обходные меры, пока не появятся патчи."
    )
    entry = _entry(
        fix="Обновление до FortiMail 7.4.9 (пока недоступно для текущих веток).", why=why
    )

    assert reconcile_fix(entry, FORTIMAIL_POST).why == why


def test_a_partial_fix_keeps_the_advice_for_the_fixed_versions_and_adds_the_caveat() -> None:
    entry = _entry(why="Обновите среды разработки CODESYS до 3.5.22.40.")

    fixed = reconcile_fix(entry, CODESYS)

    assert fixed.why == f"Обновите среды разработки CODESYS до 3.5.22.40. {PARTIAL_NOTE}"
    assert fixed.vulnerability is not None
    assert fixed.vulnerability.fix == PARTIAL_NOTE


def test_the_way_to_fix_bdu_names_does_not_count_as_a_released_update() -> None:
    """BDU:2026-15790 said "обновление программного обеспечения" on 1 October,
    before any fixed FortiMail build existed."""
    entry = _entry(why="Установите обновление.").model_copy(
        update={
            "references": (
                VulnerabilityReference(
                    id="CVE-2026-104286",
                    bdu_id="BDU:2026-15790",
                    bdu_fix="обновление программного обеспечения",
                    nvd_patch=True,
                ),
            )
        }
    )

    fixed = reconcile_fix(entry, FORTIMAIL_ENGLISH)

    assert fixed.why.startswith("Исправление ещё не выпущено")


def test_in_a_roundup_only_the_cards_own_vulnerability_decides() -> None:
    roundup = (
        "CVE-2026-1001 исправлена в версии 2.1. Для CVE-2026-1002 обновления пока недоступны. "
        "Также закрыты CVE-2026-1003, CVE-2026-1004, CVE-2026-1005 и CVE-2026-1006."
    )

    assert fix_status(VulnerabilityCard(ids=("CVE-2026-1001",)), roundup) == ""
    assert fix_status(VulnerabilityCard(ids=("CVE-2026-1002",)), roundup) == "pending"
    # A card without ids, or with one no sentence names, cannot tell whose fix is coming.
    assert fix_status(VulnerabilityCard(), roundup) == ""
    assert fix_status(VulnerabilityCard(ids=("CVE-2026-1007",)), roundup) == ""


def test_an_entry_without_a_vulnerability_card_is_left_alone() -> None:
    brief = ItemSummary(summary="Fortinet предупредила о бреши.", why="Обновите FortiMail.")

    assert reconcile_fix(brief, FORTIMAIL_POST) == brief


def test_a_workaround_step_that_says_to_update_is_left_out_while_there_is_no_fix() -> None:
    advice = pending_advice(
        "Ограничить доступ к веб-консолям из интернета; обновить компоненты Windows."
    )

    assert advice == (
        "Исправление ещё не выпущено, до его выхода: ограничить доступ к веб-консолям из интернета."
    )
    assert not advises_patch(advice)
    # Nothing left but the update: wait for the vendor.
    assert pending_advice("Обновить до версии 7.4.9.") == (
        "Исправление ещё не выпущено: следите за выходом обновления у производителя."
    )
