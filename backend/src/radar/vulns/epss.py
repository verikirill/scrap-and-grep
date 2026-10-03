"""FIRST's EPSS: how likely a CVE is to be exploited in the next 30 days.

One gzipped CSV of every CVE, about 2.7 MB (380 000 rows), scored anew once a
day. The probability says what CVSS does not: of two critical CVEs, the one
attackers are likely to use. Taken whole once a day with a conditional
request and kept in a table, so a digest never asks for it.
"""

import csv
import gzip
import io
import re
from dataclasses import asdict, dataclass
from datetime import date

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from radar.cache import Cache
from radar.db.models import EpssScore
from radar.logging import get_logger

log = get_logger(__name__)

_MODIFIED_KEY = "epss:last-modified"
_MODIFIED_TTL = 7 * 24 * 3600
# Three parameters a row: under PostgreSQL's 32 767 per statement.
_BATCH = 10_000
_SCORE_DATE_RE = re.compile(r"score_date:(\d{4}-\d{2}-\d{2})")


@dataclass(frozen=True, slots=True)
class EpssEntry:
    cve_id: str
    score: float
    percentile: float
    scored_on: date | None


def parse_scores(raw: bytes) -> list[EpssEntry]:
    """The file's rows; gzipped or not. The first line, a comment, carries the
    date the scores are for."""
    data = gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw
    lines = io.StringIO(data.decode("utf-8", errors="replace"))
    first = lines.readline()
    found = _SCORE_DATE_RE.search(first)
    scored_on = date.fromisoformat(found.group(1)) if found else None
    if not first.startswith("#"):
        lines.seek(0)
    entries = []
    for row in csv.DictReader(lines):
        try:
            entries.append(
                EpssEntry(
                    cve_id=str(row["cve"]).strip().upper(),
                    score=float(row["epss"]),
                    percentile=float(row["percentile"]),
                    scored_on=scored_on,
                )
            )
        except KeyError, TypeError, ValueError:
            continue
    return entries


async def refresh(
    session: AsyncSession, client: httpx.AsyncClient, cache: Cache, url: str
) -> tuple[int, str | None]:
    """Take the scores in if the file changed: how many are kept, and its
    Last-Modified to remember once the caller has committed them."""
    count = int(await session.scalar(select(func.count()).select_from(EpssScore)) or 0)
    headers = {}
    modified = await cache.get_json(_MODIFIED_KEY)
    if count and isinstance(modified, str):
        headers["If-Modified-Since"] = modified
    # The current file is a redirect to the day's one, on the same host: the
    # address is the operator's setting, as the other bases' are.
    response = await client.get(url, headers=headers, follow_redirects=True)
    if response.status_code == httpx.codes.NOT_MODIFIED:
        return count, None
    response.raise_for_status()
    entries = parse_scores(response.content)
    if not entries:
        log.warning("epss_empty", url=url)
        return count, None
    # Replaced whole in the caller's transaction: readers see yesterday's
    # scores until it commits.
    await session.execute(delete(EpssScore))
    for start in range(0, len(entries), _BATCH):
        rows = [asdict(entry) for entry in entries[start : start + _BATCH]]
        await session.execute(insert(EpssScore).values(rows).on_conflict_do_nothing())
    log.info("epss_refreshed", scores=len(entries), scored_on=str(entries[0].scored_on))
    return len(entries), response.headers.get("Last-Modified")


async def remember(cache: Cache, last_modified: str | None) -> None:
    if last_modified:
        await cache.set_json(_MODIFIED_KEY, last_modified, _MODIFIED_TTL)
