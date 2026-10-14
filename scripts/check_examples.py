# /// script
# requires-python = ">=3.14"
# dependencies = ["radar"]
#
# [tool.uv.sources]
# radar = { path = "../backend", editable = true }
# ///
"""Check the issues saved under a folder for entries that contradict each other.

    uv run scripts/check_examples.py examples

The same from the backend's locked environment, without building another:

    cd backend && uv run python ../scripts/check_examples.py ../examples

Every Markdown file with the "**Сформирован:**" line the renderer heads an
issue with is read, cards as "- **Поле:**" lists (issues of October 2) and as
tables (the renderer now). One line per finding, "file:line: ...". The exit
code is 1 when any of these is found:

  A   one vulnerability as two entries: their cards share a CVE or BDU id and
      selection's own rule (scoring.same_vulnerability) would have merged them;
  B1  the update row says the fix is not out, and "Почему важно" tells to
      install it (radar.fix_status, the phrases the digest itself uses);
  BP  the shift plan puts an update that is not out before the workaround;
  M   an issue for management names an id, a CVSS score or a version, what
      cards.technical_tokens keeps from a manager.

Heuristics only warn: a shared id the rule does not merge (a roundup), two
vulnerability entries whose headlines share product names and no id (A2),
advice to install an update the card does not name (B2), and an exploit
label of "нет" next to the bases or the text saying it is exploited (E).
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from radar.cards import NO_DATA, identifiers, technical_tokens
from radar.fix_status import PARTIAL_NOTE, advises_patch, row_says_pending
from radar.selection.scoring import Mentions, mentions, same_vulnerability

# The renderer heads every issue with the time it was built; READMEs, diffs,
# the analyst's answer and the resumes have no such line.
_ISSUE_RE = re.compile(r"^\*\*Сформирован:\*\*", re.MULTILINE)
_HEADING_RE = re.compile(r"^### \[((?:\\.|[^\]\\])*)\]\(([^)\s]*)\)\s*$")
_BULLET_RE = re.compile(r"^- \*\*([^*]+?):\*\*\s?(.*)$")
_CELL_RE = re.compile(r"^\| ((?:\\\||[^|])+?) \| ((?:\\\||[^|])*?) \|$")
_PLAN_ENTRY_RE = re.compile(r"^- \[ \] \[")
_PLAN_STEP_RE = re.compile(r"^  - (.*)$")
_FRONT_RE = re.compile(r"^(\w+): (.*)$")

PLAN_TITLE = "План на смену"
OVERVIEW_TITLES = ("Главное", "Что это значит для нас")
UPDATE = "Обновление"
WORKAROUND = "Временные меры"

# Advice that names what to install: "до версии 4.23", "8.3.1".
_CONCRETE_RE = re.compile(r"до\s+верси|\d+\.\d+")
_EXPLOITED_RE = re.compile(
    r"активно\s+(?:эксплуатир|использ)|используе?тся\s+в\s+(?:атаках|реальных)|"
    r"эксплуатир\w+\s+в\s+(?:атаках|реальных|дикой)|in\s+the\s+wild|actively\s+exploited",
    re.IGNORECASE,
)
_BASES_EXPLOITED_RE = re.compile(r"CISA KEV с|используется в атаках")
# Latin words of a headline that name no product: two entries sharing them
# are not one story ("Critical vulnerability in ..."). A sentence of them
# reads easier than a list of ninety strings.
_GENERIC_WORDS = (
    "critical vulnerability vulnerabilities zero days zero-day zero-days remote code execution "
    "cisa warning update updates security attack attacks flaw flaws exploited exploit exploits "
    "active under patch patches fixes with from into over about after series manager "
    "controllers controller gateway server servers systems system industrial advisory "
    "advisories path traversal denial service allows unauthenticated arbitrary file files "
    "writes hackers warns data network access multiple high severity issues release new "
    "cybersecurity threat intelligence researchers report chain linux windows android cloud "
    "edition version versions known catalog infrastructure energy facilities positive "
    "technologies group groups"
)
_GENERIC_LATIN = frozenset(_GENERIC_WORDS.split())
_ID_WORDS_RE = re.compile(r"\b(?:CVE|BDU|БДУ|GHSA)[-:\s]*[\w-]*", re.IGNORECASE)


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    check: str
    message: str
    strict: bool

    def __str__(self) -> str:
        level = "ошибка" if self.strict else "предупреждение"
        return f"{self.path.as_posix()}:{self.line}: {level} {self.check}: {self.message}"


@dataclass
class Entry:
    line: int
    headline: str
    meta: str = ""
    original: str = ""
    fields: dict[str, tuple[str, int]] = field(default_factory=dict)
    text: list[tuple[str, int]] = field(default_factory=list)
    why: tuple[str, int] = ("", 0)
    unsupported: str = ""

    def value(self, label: str) -> str:
        return self.fields.get(label, ("", 0))[0]

    def at(self, label: str) -> int:
        return self.fields.get(label, ("", self.line))[1]

    @property
    def card_ids(self) -> frozenset[str]:
        return frozenset(identifiers(f"{self.value('Идентификаторы')} {self.value('Уязвимости')}"))

    @property
    def summary(self) -> str:
        return " ".join(text for text, _ in self.text)


@dataclass
class Issue:
    path: Path
    audience: str = ""
    entries: list[Entry] = field(default_factory=list)
    # Per entry of the plan, its steps with their lines.
    plan: list[list[tuple[str, int]]] = field(default_factory=list)
    overview: list[tuple[str, int]] = field(default_factory=list)

    @property
    def for_management(self) -> bool:
        if self.audience:
            return self.audience == "management"
        # Before the front matter: only a specialist's entry shows a priority.
        return bool(self.entries) and not any("приоритет:" in e.meta for e in self.entries)


def _unescape(text: str) -> str:
    return re.sub(r"\\(.)", r"\1", text).replace("&lt;", "<").replace("&gt;", ">")


def _front_matter(lines: list[str]) -> tuple[dict[str, str], int]:
    if lines[:1] != ["---"]:
        return {}, 0
    found: dict[str, str] = {}
    for number, line in enumerate(lines[1:], 2):
        if line == "---":
            return found, number
        match = _FRONT_RE.match(line)
        if match:
            found[match.group(1)] = match.group(2).strip('"')
    return found, 0


def _entry_line(entry: Entry, line: str, number: int) -> None:
    """One line of an entry's body into its place."""
    if line.startswith("*") and " · " in line and not entry.meta:
        entry.meta = line.strip("*")
    elif line.startswith("*Нет в тексте статьи, убрано проверкой:"):
        entry.unsupported = line
    elif line.startswith("**Почему важно:**"):
        entry.why = (_unescape(line.removeprefix("**Почему важно:**").strip()), number)
    elif line.startswith("Оригинал:"):
        entry.original = _unescape(line.removeprefix("Оригинал:").strip())
    elif bullet := _BULLET_RE.match(line):
        entry.fields[bullet.group(1).strip()] = (_unescape(bullet.group(2).strip()), number)
    elif cell := _CELL_RE.match(line):
        label = _unescape(cell.group(1).strip())
        if label != "Поле" and set(label) - {"-", " "}:
            entry.fields[label] = (_unescape(cell.group(2).strip()), number)
    elif not line.startswith(("Также об этом:", "Ссылки из поста:", "**Признаки:**", "|")):
        entry.text.append((_unescape(line), number))


def parse(path: Path) -> Issue | None:
    """The issue in a Markdown file, or None for a file that is not one."""
    text = path.read_text(encoding="utf-8")
    if not _ISSUE_RE.search(text):
        return None
    lines = text.splitlines()
    front, start = _front_matter(lines)
    issue = Issue(path, audience=front.get("audience", ""))
    section = ""
    entry: Entry | None = None
    for number, raw in enumerate(lines[start:], start + 1):
        line = raw.rstrip()
        if line.startswith("## "):
            section, entry = line[3:].strip(), None
        elif line.startswith("<details>"):
            entry = None  # what was left out of the issue
        elif section == PLAN_TITLE:
            if _PLAN_ENTRY_RE.match(line):
                issue.plan.append([])
            elif (step := _PLAN_STEP_RE.match(line)) and issue.plan:
                issue.plan[-1].append((_unescape(step.group(1)), number))
        elif section in OVERVIEW_TITLES and line.startswith("- "):
            issue.overview.append((_unescape(line[2:]), number))
        elif heading := _HEADING_RE.match(line):
            entry = Entry(number, _unescape(heading.group(1)))
            entry.text.append((entry.headline, number))
            issue.entries.append(entry)
        elif entry is not None and line:
            _entry_line(entry, line, number)
    return issue


def _named(entry: Entry) -> Mentions:
    """The entry as selection sees a publication: the ids of its card and the
    Latin names of its headline."""
    return Mentions(ids=entry.card_ids, names=mentions(entry.headline, entry.summary, None).names)


def _distinctive(entry: Entry) -> set[str]:
    bare = _ID_WORDS_RE.sub(" ", f"{entry.headline} {entry.original}")
    words = {word.lower().strip("-") for word in re.findall(r"[A-Za-z][A-Za-z0-9+-]{3,}", bare)}
    return words - _GENERIC_LATIN


def check_twice(issue: Issue) -> list[Finding]:
    """A: one vulnerability as two entries; A2: perhaps one story as two."""
    found = []
    for index, right in enumerate(issue.entries):
        for left in issue.entries[:index]:
            shared = left.card_ids & right.card_ids
            if shared and same_vulnerability(_named(left), _named(right)):
                ids = ", ".join(sorted(shared))
                message = f"та же уязвимость, что в записи на строке {left.line} ({ids})"
                found.append(Finding(issue.path, right.line, "A", message, strict=True))
                break
            if shared:
                message = (
                    f"общий номер с записью на строке {left.line} ({', '.join(sorted(shared))}), "
                    "одна из них подборка: проверьте, не повтор ли это"
                )
                found.append(Finding(issue.path, right.line, "A", message, strict=False))
                break
            names = _distinctive(left) & _distinctive(right)
            both_cards = "Уязвимость" in left.fields and "Уязвимость" in right.fields
            if both_cards and len(names) >= 2 and not (left.card_ids and right.card_ids):
                message = (
                    f"возможно, та же новость, что в записи на строке {left.line}: "
                    f"общие имена {', '.join(sorted(names))}, номеров для сверки нет"
                )
                found.append(Finding(issue.path, right.line, "A2", message, strict=False))
                break
    return found


def check_advice(issue: Issue) -> list[Finding]:
    """B1: advice to install a fix the card says is not out; B2: one it does not name."""
    found = []
    for entry in issue.entries:
        why, line = entry.why
        # A partial fix with its caveat agrees: the advice is for the fixed versions.
        if not why or PARTIAL_NOTE in why or not advises_patch(why):
            continue
        row = entry.value(UPDATE)
        if row not in ("", NO_DATA) and row_says_pending(row):
            message = (
                "«Почему важно» советует поставить исправление, а строка «Обновление» "
                f"(строка {entry.at(UPDATE)}) говорит, что его ещё нет"
            )
            found.append(Finding(issue.path, line, "B1", message, strict=True))
            continue
        removed = UPDATE in entry.unsupported
        if (
            UPDATE in entry.fields
            and row in ("", NO_DATA)
            and (removed or _CONCRETE_RE.search(why))
        ):
            reason = "строку «Обновление» убрала проверка" if removed else "в карточке его нет"
            message = f"«Почему важно» советует поставить обновление, а {reason}"
            found.append(Finding(issue.path, line, "B2", message, strict=False))
    return found


def check_plan(issue: Issue) -> list[Finding]:
    """BP: the shift plan sends to install an update that is not out before the workaround."""
    found = []
    for steps in issue.plan:
        if len(steps) < 2:
            continue
        (first, line), rest = steps[0], [step for step, _ in steps[1:]]
        pending = first.startswith(f"{UPDATE}:") and row_says_pending(first)
        if pending and any(step.startswith(f"{WORKAROUND}:") for step in rest):
            message = "первый шаг плана: обновление, которого ещё нет; временные меры идут после"
            found.append(Finding(issue.path, line, "BP", message, strict=True))
    return found


def check_management(issue: Issue) -> list[Finding]:
    """M: a manager is given no ids, scores or versions, in the entries or above them."""
    if not issue.for_management:
        return []
    texts = [*issue.overview]
    for entry in issue.entries:
        texts += [*entry.text, *([entry.why] if entry.why[0] else [])]
    found = []
    for text, line in texts:
        if tokens := technical_tokens(text):
            message = f"выпуск для руководства называет {', '.join(tokens[:4])}"
            found.append(Finding(issue.path, line, "M", message, strict=True))
    return found


def check_exploit(issue: Issue) -> list[Finding]:
    """E: an exploit label of "нет" while the bases or the entry say it is exploited."""
    found = []
    for entry in issue.entries:
        label = entry.value("Эксплойт")
        if label not in ("нет", NO_DATA):
            continue
        prose = f"{entry.summary} {entry.why[0]}"
        if _BASES_EXPLOITED_RE.search(entry.value("Сверено по базам")) or _EXPLOITED_RE.search(
            prose
        ):
            message = f"эксплойт «{label}», а справка баз или текст записи говорят об атаках"
            found.append(Finding(issue.path, entry.at("Эксплойт"), "E", message, strict=False))
    return found


def check_issue(path: Path) -> list[Finding]:
    """What one saved file contradicts; nothing for a file that is no issue."""
    issue = parse(path)
    if issue is None:
        return []
    found = [
        *check_twice(issue),
        *check_advice(issue),
        *check_plan(issue),
        *check_management(issue),
        *check_exploit(issue),
    ]
    return sorted(found, key=lambda finding: finding.line)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path, help="папка с выпусками, например examples")
    args = parser.parse_args(argv)
    issues = [path for path in sorted(args.folder.rglob("*.md")) if parse(path) is not None]
    findings = [finding for path in issues for finding in check_issue(path)]
    for finding in findings:
        print(finding)
    errors = sum(finding.strict for finding in findings)
    print(
        f"Выпусков: {len(issues)}, ошибок: {errors}, предупреждений: {len(findings) - errors}.",
        file=sys.stderr,
    )
    return 1 if errors else 0


if __name__ == "__main__":
    # A Windows console is not UTF-8 by default, and every finding is Russian.
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.exit(main())
