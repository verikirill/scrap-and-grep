"""scripts/check_examples.py: a saved issue that contradicts itself fails the check.

The jury opened change/02-exclusion/after.md and saw FortiMail twice, and an
entry whose update row said the fix was not out while "Почему важно" told to
install it. The entries below are lines of the saved issues of October 2-3."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from radar.fix_status import PARTIAL_NOTE

ROOT = Path(__file__).resolve().parents[2]
# The issue the jury of the qualifying stage read, as it was saved on 02.10:
# FortiMail twice and advice to install a fix that was not out.
JURY_CASE = Path(__file__).with_name("fixtures") / "jury-fortimail-issue.md"


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "check_examples", ROOT / "scripts" / "check_examples.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


checker = _script()

SPECIALIST_META = "*SecAtor · 02.10.2026 · Уязвимость · приоритет: высокий · релевантность 0.74*"
MANAGEMENT_META = "*CNews: Безопасность · 01.10.2026 · релевантность 1.00*"

# change/02-exclusion/after.md:83, the SecAtor post.
FORTIMAIL_SECATOR = f"""### [FortiMail: критическая уязвимость с активным 0-day использованием](https://t.me/true_secator/8672)

{SPECIALIST_META}

Уязвимость CVE-2026-104286 позволяет записывать произвольные файлы в систему FortiMail.

- **Уязвимость:** уязвимость в FortiMail
- **Обновление:** Обновление до FortiMail 7.4.9, 7.6.7 или 8.0.2 (пока недоступно для текущих веток).
- **Временные меры:** Отключить функцию IBE; ограничить доступ к веб-интерфейсу FortiMail из Интернета.
- **Эксплойт:** используется в атаках
- **Идентификаторы:** CVE-2026-104286, BDU:2026-15790

**Почему важно:** Необходимо срочно применить обходные меры и установить патч, иначе подстанции могут быть скомпрометированы через FortiMail.
"""  # noqa: E501

# change/02-exclusion/after.md:127, the same vulnerability from 1275.ru.
FORTIMAIL_1275 = f"""### [CISA добавила в каталог активно эксплуатируемых уязвимостей обход пути в Fortinet FortiMail](https://1275.ru/vulnerability/fortimail_42640)

{SPECIALIST_META}

- **Уязвимость:** уязвимость в Fortinet FortiMail
- **Обновление:** Обновить до FortiMail 8.0.2, 7.6.7 или 7.4.9; для ветки 7.2 рекомендуется перейти на 7.4 или новее.
- **Эксплойт:** используется в атаках
- **Идентификаторы:** CVE-2026-104286, BDU:2026-15790

**Почему важно:** Необходимо проверить доступность веб-консоли FortiMail из интернета и установить патч, иначе система может быть скомпрометирована.
"""  # noqa: E501

# vs-analyst/assistant-ics-security-engineer.md:215, the card as a table.
FORTIMAIL_TABLE = f"""### [FortiMail: критическая уязвимость Path Traversal с удалённым выполнением кода](https://bleepingcomputer.com/news/security/fortimail)

{SPECIALIST_META}

| Поле | Значение |
| --- | --- |
| Уязвимость | уязвимость в Fortinet FortiMail |
| Обновление | Обновление до FortiMail 7.4.9, 7.6.7 или 8.0.2 (пока недоступно, ожидается). |
| Эксплойт | используется в атаках |
| Идентификаторы | CVE-2026-104286, BDU:2026-15790 |

**Почему важно:** Необходимо срочно установить патч или применить временные меры, иначе система подвержена активным zero-day атакам.
"""  # noqa: E501

# ics-security-engineer.md:290: ABB names no fix, only workarounds.
ABB = f"""### [ABB Protection and Control IED Manager PCM600](https://cisa.gov/news-events/ics-advisories/abb-pcm600)

{SPECIALIST_META}

- **Уязвимость:** уязвимость в ABB Protection and Control IED Manager PCM600
- **Обновление:** Обновить до версии выше 2.14, если доступно обновление от ABB; в текущем выпуске исправления нет.
- **Эксплойт:** нет
- **Идентификаторы:** CVE-2026-15952, CVE-2026-15953

**Почему важно:** Необходимо проверить конфигурацию службы ABBPCMSchedulerService и обновить PCM600 до версии &gt; 2.14, иначе система подвержена эскалации привилегий.
"""  # noqa: E501

# models/qwen3.5-9b/ics-security-engineer.md:155: one branch fixed, the other in Q4.
CODESYS = f"""### [Две уязвимости в CODESYS позволяют вызвать отказ в обслуживании](https://1275.ru/vulnerability/codesys_42653)

{SPECIALIST_META}

- **Уязвимость:** уязвимость в CODESYS
- **Обновление:** Обновление до версии 3.5.22.40 для Windows-платформ и до 4.23.0.0 для Linux-платформ (релиз ожидается в IV квартале 2026 года).
- **Эксплойт:** нет
- **Идентификаторы:** CVE-2026-76992, CVE-2026-79625

**Почему важно:** Инженеру необходимо срочно обновить среды разработки и исполнения до указанных версий, чтобы исключить подмену данных в диспетчерских центрах.
"""  # noqa: E501

# change/02-exclusion/after.md:105: the fix is out, the advice is right.
CISCO = f"""### [Cisco Catalyst SD-WAN Manager: критическая 0-day уязвимость CVE-2026-76504](https://t.me/true_secator/8666)

{SPECIALIST_META}

- **Уязвимость:** уязвимость в Cisco Catalyst SD-WAN Manager
- **Обновление:** Cisco выпустила обновления; требуется обновить до версии, содержащей патч, указанную в официальных рекомендациях Cisco.
- **Эксплойт:** используется в атаках
- **Идентификаторы:** CVE-2026-76504, BDU:2026-15713

**Почему важно:** Необходимо немедленно установить патч, иначе система управления SD-WAN может быть полностью захвачена злоумышленниками.
"""  # noqa: E501

# management-weekly.md:57: a manager is given no versions.
KASKAD = f"""### [Positive Technologies помогла исправить 17 уязвимостей в популярной российской SCADA-системе](https://safe.cnews.ru/news/line/kaskad)

{MANAGEMENT_META}

Эксперты нашли 17 уязвимостей в SCADA-системе «Каскад», которые могли позволить злоумышленнику управлять технологическими процессами.

**Почему важно:** Необходимо установить обновление версии 8.3.1 и ограничить доступ к компонентам SCADA из внешних сетей.
"""  # noqa: E501


# Steps of the shift plan; the first is vs-analyst/assistant-ics-security-engineer.md:51.
FORTIMAIL_STEP = (
    "  - Обновление: Обновление до FortiMail 7.4.9, 7.6.7 или 8.0.2 (пока недоступно, ожидается)."
)
WORKAROUND_STEP = "  - Временные меры: Отключить поддержку IBE."
CISCO_STEP = "  - Обновление: Cisco выпустила обновления; обновить до версии, содержащей патч."


def _issue(*entries: str, plan: str = "", audience: str = "specialist") -> str:
    """An issue as the renderer writes it: front matter, header, plan, sections."""
    head = (
        f'---\naudience: "{audience}"\n---\n\n'
        "# Критические уязвимости и новые OT-атаки в энергетике\n\n"
        "**Профиль:** Специалист по ИБ АСУ ТП (версия 1)  \n"
        "**Период:** 25.09.2026 - 02.10.2026  \n"
        "**Сформирован:** 02.10.2026 16:49 МСК\n\n"
    )
    plan_part = f"## План на смену\n\n{plan}\n" if plan else ""
    return f"{head}{plan_part}## 2. Уязвимости\n\n" + "\n".join(entries)


def _line(text: str, start: str) -> int:
    return next(n for n, line in enumerate(text.splitlines(), 1) if line.startswith(start))


def _write(folder: Path, name: str, text: str) -> Path:
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def _strict(findings: list) -> list[tuple[str, int]]:
    return [(finding.check, finding.line) for finding in findings if finding.strict]


def test_one_vulnerability_told_twice_in_an_issue_fails_the_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    text = _issue(FORTIMAIL_SECATOR, CISCO, FORTIMAIL_1275)
    path = _write(tmp_path, "after.md", text)
    again = _line(text, "### [CISA добавила в каталог")

    told_twice = [found for found in _strict(checker.check_issue(path)) if found[0] == "A"]

    assert told_twice == [("A", again)]
    assert checker.main([str(tmp_path)]) == 1
    assert f"after.md:{again}:" in capsys.readouterr().out


def test_a_roundup_that_names_one_id_of_an_entry_is_not_that_entry_again(tmp_path: Path) -> None:
    roundup = FORTIMAIL_1275.replace(
        "CVE-2026-104286, BDU:2026-15790",
        "CVE-2026-104286, CVE-2026-76504, CVE-2026-76992, CVE-2026-79625, CVE-2026-15952",
    ).replace("Fortinet FortiMail]", "дайджест трендовых уязвимостей]")
    path = _write(tmp_path, "issue.md", _issue(FORTIMAIL_1275, roundup))

    assert _strict(checker.check_issue(path)) == []


@pytest.mark.parametrize(
    "entry", [FORTIMAIL_SECATOR, FORTIMAIL_TABLE, ABB], ids=["list", "table", "abb"]
)
def test_advice_to_install_a_fix_the_card_calls_not_out_fails_the_check(
    tmp_path: Path, entry: str
) -> None:
    text = _issue(entry)
    path = _write(tmp_path, "issue.md", text)

    assert _strict(checker.check_issue(path)) == [("B1", _line(text, "**Почему важно:**"))]


@pytest.mark.parametrize(
    "why",
    [
        # it-infrastructure-lead.md:58
        "Необходимо немедленно ограничить доступ к интерфейсу управления FortiMail и применить "
        "обходные меры, пока не появятся патчи.",
        # CODESYS once the product says which versions are fixed.
        "Инженеру необходимо срочно обновить среды разработки до указанных версий. " + PARTIAL_NOTE,
    ],
    ids=["tied-to-release", "partial-fix"],
)
def test_advice_that_agrees_with_a_fix_not_out_passes(tmp_path: Path, why: str) -> None:
    entry = CODESYS.split("**Почему важно:**")[0] + f"**Почему важно:** {why}\n"
    path = _write(tmp_path, "issue.md", _issue(entry))

    assert _strict(checker.check_issue(path)) == []


@pytest.mark.parametrize(
    ("steps", "fails"),
    [
        ((FORTIMAIL_STEP, WORKAROUND_STEP), True),
        ((WORKAROUND_STEP, FORTIMAIL_STEP), False),
        ((CISCO_STEP, WORKAROUND_STEP), False),
    ],
    ids=["update-not-out-first", "workaround-first", "released-update-first"],
)
def test_a_shift_plan_fails_the_check_when_it_starts_with_a_fix_not_out(
    tmp_path: Path, steps: tuple[str, str], fails: bool
) -> None:
    heading = "- [ ] [FortiMail: критическая уязвимость](https://bleepingcomputer.com/x)"
    text = _issue(CISCO, plan="\n".join([heading, *steps]) + "\n")

    expected = [("BP", _line(text, steps[0]))] if fails else []
    assert _strict(checker.check_issue(_write(tmp_path, "issue.md", text))) == expected


def test_a_management_issue_with_a_version_or_an_id_fails_the_check(tmp_path: Path) -> None:
    management = _issue(KASKAD, audience="management")
    specialist = _issue(KASKAD.replace(MANAGEMENT_META, SPECIALIST_META))

    assert _strict(checker.check_issue(_write(tmp_path, "m.md", management))) == [
        ("M", _line(management, "**Почему важно:**"))
    ]
    assert _strict(checker.check_issue(_write(tmp_path, "s.md", specialist))) == []


def test_an_issue_without_front_matter_is_for_management_when_no_entry_has_a_priority(
    tmp_path: Path,
) -> None:
    # management-cybersecurity.md of October 2 has no front matter yet.
    management = _issue(KASKAD).split("---\n\n", 1)[1]
    specialist = management.replace(MANAGEMENT_META, SPECIALIST_META)

    assert _strict(checker.check_issue(_write(tmp_path, "m.md", management))) == [
        ("M", _line(management, "**Почему важно:**"))
    ]
    assert _strict(checker.check_issue(_write(tmp_path, "s.md", specialist))) == []


def test_advice_to_install_a_version_the_card_lacks_only_warns(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # change/01-removed-interest/after.md:189: the check took the update row out.
    entry = (
        CODESYS.replace(
            "- **Обновление:** Обновление до версии 3.5.22.40 для Windows-платформ и до 4.23.0.0 "
            "для Linux-платформ (релиз ожидается в IV квартале 2026 года).",
            "- **Обновление:** нет данных",
        )
        + "\n*Нет в тексте статьи, убрано проверкой: Обновление.*\n"
    )
    path = _write(tmp_path, "issue.md", _issue(entry))

    findings = checker.check_issue(path)

    assert [(f.check, f.strict) for f in findings] == [("B2", False)]
    assert checker.main([str(tmp_path)]) == 0
    assert "issue.md:" in capsys.readouterr().out


def test_a_clean_issue_and_files_that_are_no_issues_pass(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path, "ics.md", _issue(CISCO, FORTIMAIL_1275))
    # A README links issues and quotes their headings, but is none.
    _write(tmp_path, "README.md", "# Примеры\n\n" + FORTIMAIL_SECATOR + FORTIMAIL_SECATOR)

    assert checker.main([str(tmp_path)]) == 0
    assert ".md:" not in capsys.readouterr().out


def test_the_jurys_fortimail_in_change_exclusion_is_flagged() -> None:
    lines = JURY_CASE.read_text(encoding="utf-8").splitlines()
    secator = _line("\n".join(lines), "### [FortiMail: критическая уязвимость")
    cisa = _line("\n".join(lines), "### [CISA добавила в каталог")
    advice = next(n for n in range(secator, cisa) if lines[n - 1].startswith("**Почему важно:**"))

    findings = _strict(checker.check_issue(JURY_CASE))

    assert ("A", cisa) in findings
    assert ("B1", advice) in findings
