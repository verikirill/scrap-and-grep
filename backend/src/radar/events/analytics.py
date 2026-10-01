"""What the events say, for the administrator's analytics page.

Everything is read from the daily aggregates (schema/0002_daily.sql) except
the time of the last event. Rates are over distinct (reader, article) pairs:
"seen" counts an article the reader saw or acted on, "opened" one they
opened, "liked" one they liked or saved, "rejected" one they disliked or hid.
Days are UTC days.
"""

import asyncio
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from clickhouse_connect.driver.asyncclient import AsyncClient

from radar.events import clickhouse

# The four pair counts every breakdown shares.
_PAIRS = """
    uniqMergeIf(pairs, kind = 'seen') AS seen,
    uniqMergeIf(pairs, kind = 'open') AS opened,
    uniqMergeIf(pairs, kind IN ('like', 'save')) AS liked,
    uniqMergeIf(pairs, kind IN ('dislike', 'hide')) AS rejected
"""
_WHERE = "day BETWEEN {start:Date} AND {end:Date} AND (NOT is_guest OR {guests:Bool})"
# Below this many seen articles a rate says more about chance than about readers.
MIN_SEEN = 30
SOURCES_SHOWN = 8


@dataclass(frozen=True, slots=True)
class Period:
    start: date
    end: date
    guests: bool

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def previous(self) -> Period:
        return Period(
            self.start - timedelta(days=self.days), self.start - timedelta(days=1), self.guests
        )

    def parameters(self) -> dict[str, Any]:
        return {"start": self.start, "end": self.end, "guests": self.guests}


def wilson(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    """95% interval for a rate. Readers' pairs are not independent draws, so
    it is narrower than the truth: a guide to "too few to tell", no more."""
    if trials <= 0:
        return 0.0, 0.0
    rate = successes / trials
    spread = z * math.sqrt(rate * (1 - rate) / trials + z * z / (4 * trials * trials))
    centre = rate + z * z / (2 * trials)
    scale = 1 + z * z / trials
    return max(0.0, (centre - spread) / scale), min(1.0, (centre + spread) / scale)


def _rates(row: dict[str, Any]) -> dict[str, Any]:
    seen = int(row["seen"])
    low, high = wilson(int(row["opened"]), seen)
    return {
        **row,
        "ctr": row["opened"] / seen if seen else 0.0,
        "ctr_low": low,
        "ctr_high": high,
        "like_rate": row["liked"] / seen if seen else 0.0,
        "reject_rate": row["rejected"] / seen if seen else 0.0,
        "enough": seen >= MIN_SEEN,
    }


async def _rows(
    client: AsyncClient, select: str, period: Period, group: str = "", order: str = ""
) -> list[dict[str, Any]]:
    query = f"SELECT {select} FROM events_daily WHERE {_WHERE}"  # noqa: S608 (fixed text)
    if group:
        query += f" GROUP BY {group}"
    if order:
        query += f" ORDER BY {order}"
    result = await client.query(query, parameters=period.parameters())
    return list(result.named_results())


async def _totals(client: AsyncClient, period: Period) -> dict[str, Any]:
    [row] = await _rows(
        client,
        f"""uniqMerge(readers) AS readers, {_PAIRS},
            sumIf(events, kind = 'served') AS served,
            sumIf(events, kind = 'digest_built') AS digests_built,
            sumIf(events, kind = 'digest_opened') AS digests_opened,
            sumIf(events, kind = 'mcp_call') AS mcp_calls,
            sumIf(events, kind = 'suggestion_accepted') AS suggestions_accepted,
            sumIf(events, kind = 'suggestion_dismissed') AS suggestions_dismissed""",
        period,
    )
    return _rates(row)


def _daily(rows: Sequence[dict[str, Any]], period: Period) -> list[dict[str, Any]]:
    """One row per day of the period, days without events included."""
    by_day = {row["day"]: row for row in rows}
    empty = {"readers": 0, "seen": 0, "opened": 0, "liked": 0, "rejected": 0}
    return [
        _rates({**empty, **by_day.get(day, {}), "day": day})
        for day in (period.start + timedelta(days=offset) for offset in range(period.days))
    ]


async def overview(period: Period) -> dict[str, Any]:
    """Every panel of the page, in one round of queries."""
    breakdowns = (
        (f"day, uniqMergeIf(readers, kind = 'seen') AS readers, {_PAIRS}", "day", ""),
        (
            f"if(surface = 'digest', 'digest', slot) AS slot, {_PAIRS}",
            "slot HAVING slot != '' AND seen > 0",
            "seen DESC",
        ),
        (f"source_id, {_PAIRS}", "source_id HAVING source_id > 0", ""),
        (f"category, {_PAIRS}", "category HAVING category != '' AND seen > 0", "seen DESC"),
        (
            f"adaptive, uniqMergeIf(readers, kind = 'seen') AS readers, {_PAIRS}",
            "adaptive HAVING seen > 0",
            "adaptive DESC",
        ),
        (
            f"variant, uniqMergeIf(readers, kind = 'seen') AS readers, {_PAIRS}",
            "variant HAVING variant != '' AND seen > 0",
            "variant",
        ),
    )
    async with clickhouse.connect() as client:
        totals, previous = await asyncio.gather(
            _totals(client, period), _totals(client, period.previous())
        )
        daily, slots, sources, categories, cohorts, variants = await asyncio.gather(
            *(_rows(client, select, period, group, order) for select, group, order in breakdowns)
        )
        last = await client.query("SELECT max(ts) FROM events")
    measured = [_rates(row) for row in sources]
    trusted = [row for row in measured if row["enough"]]
    last_event: datetime | None = last.result_rows[0][0] if last.result_rows else None
    return {
        "totals": totals,
        "previous": previous,
        "daily": _daily(daily, period),
        "slots": [_rates(row) for row in slots],
        "sources_best": sorted(trusted, key=lambda row: -row["ctr"])[:SOURCES_SHOWN],
        "sources_rejected": sorted(
            (row for row in trusted if row["rejected"]), key=lambda row: -row["reject_rate"]
        )[:SOURCES_SHOWN],
        "categories": [_rates(row) for row in categories],
        "adaptation": [_rates(row) for row in cohorts],
        "variants": [_rates(row) for row in variants],
        # An empty table answers with the epoch.
        "last_event_at": last_event if last_event and last_event.year > 1970 else None,
    }
