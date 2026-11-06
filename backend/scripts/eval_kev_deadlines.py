"""How many CISA KEV deadlines a weekly review misses and a daily digest keeps.

    uv run python scripts/eval_kev_deadlines.py --start 2026-07-01 --end 2026-09-30 \\
        --out ../docs/eval/kev-deadlines.md

Question. CISA gives most vulnerabilities it adds to the KEV catalogue three
days to fix. A review collected by hand once a week reaches its reader days
after the vulnerability was added; the assistant polls its sources every 15
minutes and its digest goes out every morning. On the catalogue itself: how
many deadlines had passed by the time each of them came out?

Method. Every entry the local copy of KEV (refreshed by the ingest worker)
added between --start and --end, with a deadline. The weekly review goes out
on Monday morning and carries what was added up to Sunday, so an entry added
on Monday waits seven days and one added on Sunday one day. The daily digest
goes out the next morning. An entry counts as missed when its issue comes out
after the deadline, and as too late when on the deadline day or after: on
that day there is no time left to plan the fix.
"""

import argparse
import asyncio
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import select

from radar.db import session_scope
from radar.db.models import KnownExploitedVulnerability

SHORT = 7


@dataclass(frozen=True)
class Entry:
    cve_id: str
    added: date
    due: date

    @property
    def window(self) -> int:
        return (self.due - self.added).days


def weekly_issue(added: date) -> date:
    """The next Monday after the day the entry was added."""
    return added + timedelta(days=7 - added.weekday())


def daily_issue(added: date) -> date:
    return added + timedelta(days=1)


async def load(start: date, end: date) -> list[Entry]:
    async with session_scope() as session:
        rows = await session.execute(
            select(
                KnownExploitedVulnerability.cve_id,
                KnownExploitedVulnerability.date_added,
                KnownExploitedVulnerability.due_date,
            ).where(
                KnownExploitedVulnerability.date_added.between(start, end),
                KnownExploitedVulnerability.due_date.is_not(None),
            )
        )
        return [Entry(cve, added, due) for cve, added, due in rows]


def _mean(values: list[int]) -> str:
    return f"{sum(values) / len(values):.1f}".replace(".", ",") if values else "-"


def report(entries: list[Entry], start: date, end: date) -> str:
    short = [e for e in entries if e.window <= SHORT]
    lines = [
        "# Сроки CISA KEV: недельный обзор и выпуск каждое утро",
        "",
        f"Записи каталога CISA KEV, добавленные с {start:%d.%m.%Y} по {end:%d.%m.%Y}, "
        "со сроком устранения: "
        f"**{len(entries)}**. Срок {SHORT} дней и короче у {len(short)}. "
        "Посчитано скриптом `backend/scripts/eval_kev_deadlines.py` по локальной копии каталога, "
        "которую обновляет воркер сбора.",
        "",
        "Недельный обзор выходит в понедельник утром и несёт всё, что добавлено до воскресенья. "
        "Выпуск ассистента выходит каждое утро: источники он опрашивает каждые 15 минут. "
        "«После срока» - выпуск вышел, когда срок уже прошёл; «в день срока или позже» - "
        "на исправление не осталось ни дня.",
        "",
        "| | Недельный обзор | Выпуск каждое утро |",
        "|---|---|---|",
    ]
    rows = {
        "Дней от добавления до выпуска, в среднем": (
            _mean([(weekly_issue(e.added) - e.added).days for e in entries]),
            _mean([(daily_issue(e.added) - e.added).days for e in entries]),
        ),
        "Вышел после срока": (
            str(sum(weekly_issue(e.added) > e.due for e in entries)),
            str(sum(daily_issue(e.added) > e.due for e in entries)),
        ),
        "Вышел в день срока или позже": (
            str(sum(weekly_issue(e.added) >= e.due for e in entries)),
            str(sum(daily_issue(e.added) >= e.due for e in entries)),
        ),
        f"Осталось дней до срока, у записей со сроком до {SHORT} дней": (
            _mean([max((e.due - weekly_issue(e.added)).days, 0) for e in short]),
            _mean([max((e.due - daily_issue(e.added)).days, 0) for e in short]),
        ),
    }
    lines += [f"| {name} | {weekly} | {daily} |" for name, (weekly, daily) in rows.items()]
    windows = Counter(e.window for e in entries)
    lines += [
        "",
        "Сроки в каталоге за период:",
        "",
        "| Дней на устранение | Записей |",
        "|---|---|",
        *(f"| {days} | {count} |" for days, count in sorted(windows.items())),
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    text = report(asyncio.run(load(args.start, args.end)), args.start, args.end)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
