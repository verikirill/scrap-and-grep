"""scripts/eval_duplicates.py: every example issue is checked for retellings.

The script read only the top of examples/, so the issues of change/, models/
and vs-analyst/ were never checked, and the FortiMail told twice in
change/02-exclusion/after.md went unseen."""

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

from radar.render.markdown import render_markdown
from radar.selection.scoring import mentions
from radar.text import content_hash
from radar.views import DigestView

ROOT = Path(__file__).resolve().parents[2]
DIGEST = ROOT / "docs" / "eval" / "human" / "ics-security-engineer.digest.json"
# What else lies among the examples, in brief: links and headings, no issue header.
NOT_ISSUES = {
    "README.md": "# Примеры\n\n[ics-security-engineer.md](ics-security-engineer.md) - выпуск.\n",
    "models/README.md": "# Сравнение моделей\n\n| gpt-oss-120b | [выпуск](gpt-oss-120b/x.md) |\n",
    "change/02-exclusion/diff.md": (
        "# Добавлено исключение «уязвимости продуктов Citrix»\n\n## Пришло (1)\n\n"
        "- [FortiMail: критическая уязвимость](https://t.me/true_secator/8672) - SecAtor.\n"
    ),
    "vs-analyst/analyst-answer.md": (
        "# Аналитический отчет: Ландшафт киберугроз\n\n## Комплексный анализ\n\n"
        "### Векторы атак на критическую инфраструктуру\n\nПромышленность стала целью.\n"
    ),
    "resumes/ml-engineer.md": "# Дмитрий Кузнецов\n\n**Инженер по машинному обучению**\n",
}


def _script() -> ModuleType:
    path = ROOT / "backend" / "scripts" / "eval_duplicates.py"
    spec = importlib.util.spec_from_file_location("eval_duplicates", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


duplicates = _script()


def _story(url: str, source: str, title: str, summary: str) -> Any:
    """A publication of the snapshot, as the script reads it."""
    return duplicates.Item(
        url=url,
        source=source,
        title=title,
        published=datetime(2026, 10, 1, 12, tzinfo=UTC),
        hash=content_hash(title, summary),
        named=mentions(title, summary, None),
    )


def _issue(*stories: Any) -> str:
    """The header of an issue and an entry heading per story, as the renderer writes them."""
    entries = "\n\n".join(f"### [{story.title}]({story.url})" for story in stories)
    return (
        "# Критические уязвимости и новые OT-атаки в энергетике\n\n"
        "**Профиль:** Специалист по ИБ АСУ ТП (версия 1)  \n"
        "**Период:** 25.09.2026 - 02.10.2026  \n"
        "**Сформирован:** 02.10.2026 16:49 МСК\n\n"
        f"## Уязвимости\n\n{entries}\n"
    )


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def test_a_vulnerability_told_twice_in_an_issue_of_a_subfolder_is_found(tmp_path: Path) -> None:
    """From the snapshot: the FortiMail zero-day from SecAtor and from 1275, both
    entries of change/02-exclusion/after.md built on October 2."""
    secator = _story(
        "https://t.me/true_secator/8672",
        "tg-true-secator",
        "Fortinet предупреждает о критической уязвимости, которая активно используется",
        "CVE-2026-104286 классифицируется как критическая и затрагивает интерфейс FortiMail.",
    )
    cisa = _story(
        "https://1275.ru/vulnerability/cisa-dobavila-v-katalog-aktivno-ekspluatiruemyh-uyazvimostey-obhod-puti-v-fortinet-fortimail_42640",
        "1275",
        "CISA добавила в каталог активно эксплуатируемых уязвимостей обход пути в FortiMail",
        "CISA добавило в каталог KEV CVE-2026-104286 в почтовом шлюзе Fortinet FortiMail.",
    )
    cisco = _story(
        "https://t.me/ZerodayAlert/858",
        "tg-zerodayalert",
        "Cisco закрыла критическую zero-day в Catalyst SD-WAN Manager с CVSS 9,8",
        "CVE-2026-76504 уже применяли в реальных атаках до публичного раскрытия 30 сентября.",
    )
    examples = tmp_path / "examples"
    _write(examples / "ics-security-engineer.md", _issue(cisco))
    _write(examples / "change" / "02-exclusion" / "after.md", _issue(secator, cisco, cisa))

    report = duplicates.merged_in_examples(examples, [secator, cisa, cisco])

    assert report == [
        ("change/02-exclusion/after.md", 3, [(secator, cisa)]),
        ("ics-security-engineer.md", 1, []),
    ]


def test_readmes_diffs_the_analysts_answer_and_a_resume_are_not_taken_for_issues(
    tmp_path: Path,
) -> None:
    # An issue as the renderer writes it now, so the check follows the renderer.
    view = DigestView.model_validate_json(DIGEST.read_bytes())
    examples = tmp_path / "examples"
    _write(examples / "vs-analyst" / "assistant-ics-security-engineer.md", render_markdown(view))
    for name, text in NOT_ISSUES.items():
        _write(examples / name, text)

    report = duplicates.merged_in_examples(examples, [])

    entries = sum(len(topic.items) for topic in view.topics)
    assert report == [("vs-analyst/assistant-ics-security-engineer.md", entries, [])]
