"""The CISA catalogue of Known Exploited Vulnerabilities (KEV).

One JSON file of about 1 700 entries, 1.7 MB (190 KB gzipped), updated a few
times a week. A vulnerability on it is exploited in the wild: by the
organizers' dataset that is what puts it at the top of a specialist's digest.
The file is taken whole and kept in a table; an unchanged one costs a 304.
"""

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from radar.cache import Cache
from radar.db.models import KnownExploitedVulnerability
from radar.logging import get_logger

log = get_logger(__name__)

# The Last-Modified of the copy in the table, for a conditional request.
_MODIFIED_KEY = "kev:last-modified"
_MODIFIED_TTL = 7 * 24 * 3600


@dataclass(frozen=True, slots=True)
class KevEntry:
    cve_id: str
    vendor: str
    product: str
    name: str
    date_added: date
    ransomware: bool
    description: str
    action: str
    # The date federal agencies must fix it by, and the weaknesses it names.
    due_date: date | None = None
    cwes: tuple[str, ...] = ()


def parse_catalog(raw: dict[str, Any]) -> list[KevEntry]:
    """The catalogue's entries; one with a field of an unexpected shape is
    skipped, not allowed to lose the rest."""
    entries = []
    for item in raw.get("vulnerabilities") or []:
        try:
            entries.append(
                KevEntry(
                    cve_id=str(item["cveID"]).strip().upper(),
                    vendor=str(item.get("vendorProject") or ""),
                    product=str(item.get("product") or ""),
                    name=str(item.get("vulnerabilityName") or ""),
                    date_added=date.fromisoformat(str(item["dateAdded"])),
                    ransomware=str(item.get("knownRansomwareCampaignUse")) == "Known",
                    description=str(item.get("shortDescription") or ""),
                    action=str(item.get("requiredAction") or ""),
                    due_date=date.fromisoformat(str(item["dueDate"]))
                    if item.get("dueDate")
                    else None,
                    cwes=tuple(str(cwe) for cwe in item.get("cwes") or () if str(cwe)),
                )
            )
        except KeyError, TypeError, ValueError:
            log.warning("kev_entry_skipped", entry=str(item)[:200])
    return entries


async def refresh(
    session: AsyncSession, client: httpx.AsyncClient, cache: Cache, url: str
) -> tuple[int, str | None]:
    """Take the catalogue in if it changed. The number of entries now kept, and
    the file's Last-Modified to remember once the caller has committed them."""
    count = await session.scalar(select(func.count()).select_from(KnownExploitedVulnerability))
    # Rows from before the due date was kept take the whole file again once.
    undated = await session.scalar(
        select(func.count())
        .select_from(KnownExploitedVulnerability)
        .where(KnownExploitedVulnerability.due_date.is_(None))
    )
    headers = {}
    modified = await cache.get_json(_MODIFIED_KEY)
    # An empty table needs the file whatever the cache remembers.
    if count and not undated and isinstance(modified, str):
        headers["If-Modified-Since"] = modified
    response = await client.get(url, headers=headers)
    if response.status_code == httpx.codes.NOT_MODIFIED:
        return int(count or 0), None
    response.raise_for_status()
    entries = parse_catalog(response.json())
    for start in range(0, len(entries), 500):
        rows = [
            {**asdict(entry), "cwes": list(entry.cwes)} for entry in entries[start : start + 500]
        ]
        statement = insert(KnownExploitedVulnerability).values(rows)
        await session.execute(
            statement.on_conflict_do_update(
                index_elements=[KnownExploitedVulnerability.cve_id],
                set_={
                    column: statement.excluded[column]
                    for column in (
                        "vendor",
                        "product",
                        "name",
                        "date_added",
                        "ransomware",
                        "description",
                        "action",
                        "due_date",
                        "cwes",
                    )
                },
            )
        )
    if not entries:
        # A file of another shape: the old catalogue stays, and it is fetched whole again.
        log.warning("kev_empty", url=url)
        return int(count or 0), None
    log.info("kev_refreshed", entries=len(entries))
    return len(entries), response.headers.get("Last-Modified")


async def remember(cache: Cache, last_modified: str | None) -> None:
    if last_modified:
        await cache.set_json(_MODIFIED_KEY, last_modified, _MODIFIED_TTL)
