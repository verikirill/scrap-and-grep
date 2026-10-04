"""NVD's record of a CVE, kept locally so a digest never asks NVD while it is
being made.

Two ways in, both through NVD's API 2.0. Every hour the CVEs NVD changed
since the last round, usually one page of a few hundred: new ones arrive
before an article names them, and kept ones get their score and SSVC
assessment as NVD adds them. Then the CVEs the articles of the last month
name that are not kept yet, a few dozen a round: an article about a
two-year-old CVE exploited again needs its record too. Without a key NVD
answers five requests in 30 seconds; RADAR_NVD_API_KEY raises that to fifty.

From a record we keep what a vulnerability card can use: the CVSS score and
vector (3.x first, which the card reads in words, then 4.0 and 2.0), the
CWEs, the vulnerable products, CISA's SSVC "exploitation" and the references
NVD tagged as an exploit or a patch.
"""

import asyncio
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from radar.cache import Cache
from radar.db.models import NvdVulnerability
from radar.logging import get_logger
from radar.text import truncate

log = get_logger(__name__)

# The end of the last window taken in, for the next round to start from.
_CURSOR_KEY = "nvd:cursor"
_CURSOR_TTL = 30 * 24 * 3600
# NVD takes a window of at most 120 days; a stack off for longer starts anew.
_MAX_WINDOW = timedelta(days=119)
_FIRST_WINDOW = timedelta(days=1)
_PAGE = 2000
# Pauses between requests that keep under NVD's limits, with and without a key.
PAUSE_WITH_KEY = 0.7
PAUSE_WITHOUT_KEY = 6.5
# What an article names: the CVEs of the last month, a few dozen a round;
# 30 requests without a key take 3 minutes, under the 5 the ingest queue
# gives a task before another worker takes it over.
BACKFILL_DAYS = 30
BACKFILL_LIMIT = 30
# A CVE NVD did not have (reserved, or published a moment ago) is asked again later.
ABSENT = "Absent"
_ABSENT_RETRY = timedelta(days=3)
_LINKS = 3
_PRODUCTS = 6
_CVE_RE = re.compile(r"^CVE-\d{4}-\d{4,7}$")
# The weaknesses NVD writes when it has none to name.
_NO_CWE = {"NVD-CWE-noinfo", "NVD-CWE-Other"}
# 3.x is what the card puts in words; the primary (NVD's own) score before a CNA's.
_CVSS_ORDER = ("cvssMetricV31", "cvssMetricV30", "cvssMetricV40", "cvssMetricV2")


@dataclass(frozen=True, slots=True)
class NvdEntry:
    cve_id: str
    status: str
    published: date | None
    last_modified: datetime | None
    description: str = ""
    cvss_version: str = ""
    cvss_score: str = ""
    cvss_vector: str = ""
    severity: str = ""
    cwes: tuple[str, ...] = ()
    exploitation: str = ""
    exploit_links: tuple[str, ...] = ()
    patch_links: tuple[str, ...] = ()
    products: tuple[str, ...] = ()


def _when(value: Any) -> datetime | None:
    try:
        moment = datetime.fromisoformat(str(value))
    except TypeError, ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _cvss(metrics: dict[str, Any]) -> tuple[str, str, str, str]:
    """Version, score, vector and severity of the score to show."""
    for key in _CVSS_ORDER:
        entries = [entry for entry in metrics.get(key) or [] if isinstance(entry, dict)]
        entries.sort(key=lambda entry: entry.get("type") != "Primary")
        for entry in entries:
            data = entry.get("cvssData") or {}
            score = data.get("baseScore")
            if score is None:
                continue
            severity = data.get("baseSeverity") or entry.get("baseSeverity") or ""
            # A 4.0 vector spells out every metric left "not defined" (E:X, CR:X...).
            vector = "/".join(
                part
                for part in str(data.get("vectorString") or "").split("/")
                if not part.endswith(":X")
            )
            return (
                str(data.get("version") or ""),
                f"{float(score):g}",
                vector,
                str(severity).lower(),
            )
    return "", "", "", ""


def _exploitation(metrics: dict[str, Any]) -> str:
    """CISA's SSVC decision on exploitation: active, poc or none."""
    for entry in metrics.get("ssvcV203") or []:
        for option in (entry.get("ssvcData") or {}).get("options") or []:
            value = option.get("exploitation") if isinstance(option, dict) else None
            if value in ("active", "poc", "none"):
                return str(value)
    return ""


def _products(cve: dict[str, Any]) -> tuple[str, ...]:
    """Vendor and product of the vulnerable configurations, or of the CNA's
    "affected" list when NVD has not analysed the CVE yet."""
    found: list[str] = []
    for configuration in cve.get("configurations") or []:
        for node in configuration.get("nodes") or []:
            for match in node.get("cpeMatch") or []:
                parts = str(match.get("criteria") or "").split(":")
                if match.get("vulnerable") and len(parts) > 4:
                    found.append(f"{parts[3]} {parts[4]}".replace("_", " "))
    if not found:
        for affected in cve.get("affected") or []:
            for data in affected.get("affectedData") or []:
                vendor, product = str(data.get("vendor") or ""), str(data.get("product") or "")
                if product and product.lower() != "n/a":
                    found.append(f"{vendor} {product}".strip() if vendor != "n/a" else product)
    return tuple(dict.fromkeys(found))[:_PRODUCTS]


def _links(cve: dict[str, Any], tag: str) -> tuple[str, ...]:
    links = [
        str(reference["url"])
        for reference in cve.get("references") or []
        if tag in (reference.get("tags") or []) and reference.get("url")
    ]
    return tuple(dict.fromkeys(links))[:_LINKS]


def parse_cve(cve: dict[str, Any]) -> NvdEntry | None:
    """One record of the API's "vulnerabilities" list; None when it has no id."""
    cve_id = str(cve.get("id") or "").strip().upper()
    if not _CVE_RE.match(cve_id):
        return None
    metrics = cve.get("metrics") or {}
    version, score, vector, severity = _cvss(metrics)
    description = next(
        (
            str(item.get("value") or "")
            for item in cve.get("descriptions") or []
            if item.get("lang") == "en"
        ),
        "",
    )
    cwes = [
        str(item.get("value") or "")
        for weakness in cve.get("weaknesses") or []
        for item in weakness.get("description") or []
    ]
    published = _when(cve.get("published"))
    return NvdEntry(
        cve_id=cve_id,
        status=str(cve.get("vulnStatus") or ""),
        published=published.date() if published else None,
        last_modified=_when(cve.get("lastModified")),
        description=truncate(description, 600),
        cvss_version=version,
        cvss_score=score,
        cvss_vector=vector,
        severity=severity,
        cwes=tuple(dict.fromkeys(cwe for cwe in cwes if cwe.startswith("CWE-"))),
        exploitation=_exploitation(metrics),
        exploit_links=_links(cve, "Exploit"),
        patch_links=_links(cve, "Patch"),
        products=_products(cve),
    )


def parse_page(raw: dict[str, Any]) -> list[NvdEntry]:
    entries = []
    for item in raw.get("vulnerabilities") or []:
        try:
            entry = parse_cve(item.get("cve") or {})
        except AttributeError, TypeError, ValueError:
            log.warning("nvd_entry_skipped", entry=str(item)[:200])
            continue
        if entry is not None:
            entries.append(entry)
    return entries


async def store(
    session: AsyncSession, entries: Sequence[NvdEntry], now: datetime | None = None
) -> None:
    """Upsert, the last version winning; checked_at marks when it was taken,
    by the caller's clock when it has one."""
    now = now or datetime.now(UTC)
    unique = {entry.cve_id: entry for entry in entries}
    columns = [field for field in NvdEntry.__dataclass_fields__ if field != "cve_id"]
    rows = [
        {
            **{
                key: list(value) if isinstance(value, tuple) else value
                for key, value in asdict(entry).items()
            },
            "checked_at": now,
        }
        for entry in unique.values()
    ]
    for start in range(0, len(rows), 500):
        statement = insert(NvdVulnerability).values(rows[start : start + 500])
        await session.execute(
            statement.on_conflict_do_update(
                index_elements=[NvdVulnerability.cve_id],
                set_={column: statement.excluded[column] for column in [*columns, "checked_at"]},
            )
        )


async def _get(
    client: httpx.AsyncClient, url: str, params: dict[str, str | int], key: str
) -> dict[str, Any]:
    headers = {"apiKey": key} if key else {}
    response = await client.get(url, params=params, headers=headers)
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    return data


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000+00:00")


async def refresh_changed(
    session: AsyncSession,
    client: httpx.AsyncClient,
    cache: Cache,
    url: str,
    key: str = "",
    pause: float | None = None,
    now: datetime | None = None,
) -> tuple[int, str | None]:
    """The CVEs NVD changed since the last round: how many were taken in, and
    the window's end to remember once the caller has committed them."""
    end = now or datetime.now(UTC)
    remembered = _when(await cache.get_json(_CURSOR_KEY))
    start = remembered or end - _FIRST_WINDOW
    start = max(start, end - _MAX_WINDOW)
    wait = (PAUSE_WITH_KEY if key else PAUSE_WITHOUT_KEY) if pause is None else pause
    taken, index = 0, 0
    while True:
        page = await _get(
            client,
            url,
            {
                "lastModStartDate": _stamp(start),
                "lastModEndDate": _stamp(end),
                "resultsPerPage": _PAGE,
                "startIndex": index,
            },
            key,
        )
        entries = parse_page(page)
        await store(session, entries, end)
        taken += len(entries)
        index += int(page.get("resultsPerPage") or _PAGE)
        if index >= int(page.get("totalResults") or 0):
            break
        await asyncio.sleep(wait)
    log.info("nvd_changed", taken=taken, since=start.isoformat())
    return taken, end.isoformat()


async def remember(cache: Cache, cursor: str | None) -> None:
    if cursor:
        await cache.set_json(_CURSOR_KEY, cursor, _CURSOR_TTL)


async def named_but_missing(session: AsyncSession, now: datetime, limit: int) -> list[str]:
    """CVEs the articles of the last month name that are not kept, newest
    articles first; one NVD did not have is asked again after a few days."""
    rows = await session.execute(
        text(
            """
            SELECT cve FROM (
                SELECT DISTINCT ON (cve) cve, published_at FROM (
                    SELECT upper((regexp_matches(
                               coalesce(title, '') || ' ' || coalesce(content, ''),
                               'CVE-\\d{4}-\\d{4,7}', 'gi'))[1]) AS cve,
                           published_at
                    FROM articles
                    WHERE published_at >= :since
                ) AS named
                ORDER BY cve, published_at DESC
            ) AS latest
            ORDER BY published_at DESC
            """
        ),
        {"since": now - timedelta(days=BACKFILL_DAYS)},
    )
    named = [str(cve) for (cve,) in rows]
    if not named:
        return []
    kept = set(
        await session.scalars(
            select(NvdVulnerability.cve_id).where(
                NvdVulnerability.cve_id.in_(named),
                or_(
                    NvdVulnerability.status != ABSENT,
                    NvdVulnerability.checked_at > now - _ABSENT_RETRY,
                ),
            )
        )
    )
    return [cve for cve in named if cve not in kept][:limit]


async def backfill(
    session: AsyncSession,
    client: httpx.AsyncClient,
    url: str,
    key: str = "",
    pause: float | None = None,
    limit: int = BACKFILL_LIMIT,
    now: datetime | None = None,
) -> int:
    """Records for the CVEs the articles name and the table lacks, one request
    each; how many were asked. A failed request ends the round, the rest wait."""
    moment = now or datetime.now(UTC)
    wanted = await named_but_missing(session, moment, limit)
    wait = (PAUSE_WITH_KEY if key else PAUSE_WITHOUT_KEY) if pause is None else pause
    for number, cve in enumerate(wanted):
        if number:
            await asyncio.sleep(wait)
        try:
            page = await _get(client, url, {"cveId": cve}, key)
        except httpx.HTTPError as exc:
            log.warning("nvd_backfill_stopped", cve=cve, error=f"{type(exc).__name__}: {exc}"[:200])
            return number
        entries = [entry for entry in parse_page(page) if entry.cve_id == cve]
        await store(
            session,
            entries or [NvdEntry(cve_id=cve, status=ABSENT, published=None, last_modified=None)],
            moment,
        )
    if wanted:
        log.info("nvd_backfilled", asked=len(wanted))
    return len(wanted)
