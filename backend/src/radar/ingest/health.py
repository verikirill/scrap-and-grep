"""How the sources are doing: what the analyst the assistant replaces would
notice himself.

Every poll is kept for a week (source_polls): its status, the kind of its
error and how many articles it brought. From them: the share of good polls
in a day, the errors by kind, the sources that fail, and those that have
been silent longer than ever in the last month. The ingest worker writes the same to
its log every hour.
"""

import ssl
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import httpx
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from radar.db.models import Source, SourcePoll
from radar.ingest.fetch import Blocked
from radar.ingest.net import UnresolvableHostError, UnsafeUrlError
from radar.ingest.pages import MarkupChanged

KEEP = timedelta(days=7)
WINDOW = timedelta(hours=24)
# Failed this many polls in a row: the source is not being read.
FAILING_AFTER = 3
# Silent: no article for longer than the longest pause between two of its
# articles in the last 30 days, and a day at the least, among sources that
# wrote five times or more. A mean gap would call every weekend a silence:
# on Saturday, October 3, it named 22 sources that write hourly on weekdays.
SILENT_AT_LEAST = timedelta(days=1)
SILENT_HISTORY_DAYS = 30
SILENT_MIN_ARTICLES = 5

# The kinds of failure, as a reader calls them.
ERROR_KINDS: dict[str, str] = {
    "dns": "нет такого имени",
    "tls": "сертификат",
    "refused": "отказ сайта",
    "stub": "заглушка защиты",
    "timeout": "нет ответа",
    "connect": "нет соединения",
    "http": "ошибка сервера",
    "markup": "разметка изменилась",
    "unsafe": "внутренний адрес",
    "other": "другое",
}


def error_kind(exc: BaseException) -> str:
    """The kind of a poll's failure, from its exception."""
    if isinstance(exc, UnresolvableHostError):
        return "dns"
    if isinstance(exc, UnsafeUrlError):
        return "unsafe"
    if isinstance(exc, Blocked):
        stub = any("заглушка" in reason for _, reason in exc.attempts)
        return "stub" if stub else "refused"
    if isinstance(exc, MarkupChanged) or (
        isinstance(exc, ValueError) and str(exc).startswith("not a feed")
    ):
        return "markup"
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return "refused" if code in {401, 403, 429} else "http"
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return "timeout"
    if isinstance(exc, ssl.SSLError) or "CERTIFICATE" in str(exc).upper():
        return "tls"
    if isinstance(exc, (httpx.NetworkError, httpx.ProxyError, OSError)):
        return "connect"
    return "other"


async def record_poll(
    session: AsyncSession, source_id: int, *, status: str, kind: str | None, new: int
) -> None:
    session.add(SourcePoll(source_id=source_id, status=status, error_kind=kind, new_articles=new))


async def purge(session: AsyncSession, now: datetime) -> int:
    result = await session.execute(delete(SourcePoll).where(SourcePoll.polled_at < now - KEEP))
    return int(getattr(result, "rowcount", 0) or 0)


@dataclass(slots=True)
class Failing:
    source_id: int
    name: str
    failures: int
    kind: str | None
    error: str | None
    since: datetime | None


@dataclass(slots=True)
class Silent:
    source_id: int
    name: str
    last_article: datetime
    longest_gap_hours: float


@dataclass(slots=True)
class Health:
    hours: int
    polls: int
    ok: int
    errors: dict[str, int] = field(default_factory=dict)
    failing: list[Failing] = field(default_factory=list)
    silent: list[Silent] = field(default_factory=list)


async def health(session: AsyncSession, now: datetime) -> Health:
    since = now - WINDOW
    counts = (
        await session.execute(
            select(SourcePoll.status, SourcePoll.error_kind, func.count())
            .join(Source, Source.id == SourcePoll.source_id)
            .where(SourcePoll.polled_at >= since, Source.enabled)
            .group_by(SourcePoll.status, SourcePoll.error_kind)
        )
    ).all()
    polls = sum(count for _, _, count in counts)
    ok = sum(count for status, _, count in counts if status != "error")
    errors: dict[str, int] = {}
    for status, kind, count in counts:
        if status == "error":
            errors[kind or "other"] = errors.get(kind or "other", 0) + count

    failing_rows = (
        await session.execute(
            select(Source)
            .where(Source.enabled, Source.consecutive_failures >= FAILING_AFTER)
            .order_by(Source.consecutive_failures.desc(), Source.name)
        )
    ).scalars()
    failing = []
    for source in failing_rows:
        last = await session.scalar(
            select(SourcePoll.error_kind)
            .where(SourcePoll.source_id == source.id, SourcePoll.status == "error")
            .order_by(SourcePoll.polled_at.desc())
            .limit(1)
        )
        last_good = await session.scalar(
            select(func.max(SourcePoll.polled_at)).where(
                SourcePoll.source_id == source.id, SourcePoll.status != "error"
            )
        )
        failing.append(
            Failing(
                source_id=source.id,
                name=source.name,
                failures=source.consecutive_failures,
                kind=last,
                error=source.last_error,
                since=last_good,
            )
        )

    silent_rows = (
        await session.execute(
            text(
                """
                WITH recent AS (
                    SELECT source_id, published_at,
                           published_at - lag(published_at) OVER (
                               PARTITION BY source_id ORDER BY published_at
                           ) AS pause
                    FROM articles
                    WHERE published_at >= :history AND published_at <= :now
                ),
                per_source AS (
                    SELECT source_id, count(*) AS n, max(published_at) AS last,
                           max(pause) AS longest
                    FROM recent GROUP BY source_id
                )
                SELECT s.id, s.name, r.last, extract(epoch FROM r.longest) AS gap
                FROM sources s JOIN per_source r ON r.source_id = s.id
                WHERE s.enabled AND r.n >= :min_articles
                ORDER BY s.name
                """
            ),
            {
                "history": now - timedelta(days=SILENT_HISTORY_DAYS),
                "now": now,
                "min_articles": SILENT_MIN_ARTICLES,
            },
        )
    ).all()
    silent = [
        Silent(source_id=row.id, name=row.name, last_article=row.last, longest_gap_hours=gap / 3600)
        for row in silent_rows
        if (gap := float(row.gap or 0)) > 0
        and now - row.last > max(SILENT_AT_LEAST, timedelta(seconds=gap))
    ]
    return Health(
        hours=int(WINDOW.total_seconds() // 3600),
        polls=polls,
        ok=ok,
        errors=dict(sorted(errors.items(), key=lambda item: -item[1])),
        failing=failing,
        silent=silent,
    )
