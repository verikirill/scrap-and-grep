"""MITRE ATT&CK techniques, the reference an attack card's techniques are
checked against.

The enterprise matrix is one STIX bundle of about 45 MB, updated a couple of
times a year; the loader takes it once a day with a conditional request and
keeps only the id and the name of each technique. Until the table has been
filled, and in a closed network that never fills it, the snapshot shipped
with the package answers instead (backend/scripts/attack_snapshot.py). The
snapshot also carries the ICS matrix, which an energy company's attacks name
and the table does not keep.
"""

import json
from collections.abc import Sequence
from functools import cache
from importlib.resources import files
from typing import Any

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from radar.cache import Cache
from radar.db.models import AttackTechniqueRow
from radar.logging import get_logger

log = get_logger(__name__)

_ETAG_KEY = "attack:etag"
_ETAG_TTL = 30 * 24 * 3600


def parse_stix(raw: dict[str, Any]) -> dict[str, str]:
    """Technique id to name; revoked and deprecated techniques are left out."""
    techniques: dict[str, str] = {}
    for item in raw.get("objects") or []:
        if not isinstance(item, dict) or item.get("type") != "attack-pattern":
            continue
        if item.get("revoked") or item.get("x_mitre_deprecated"):
            continue
        for reference in item.get("external_references") or []:
            if reference.get("source_name") == "mitre-attack" and reference.get("external_id"):
                techniques[str(reference["external_id"])] = str(item.get("name") or "")
    return techniques


@cache
def snapshot() -> dict[str, str]:
    """The techniques shipped with the package."""
    text = files("radar.vulns").joinpath("attack_snapshot.json").read_text(encoding="utf-8")
    data: dict[str, str] = json.loads(text)
    return data


async def refresh(
    session: AsyncSession, client: httpx.AsyncClient, cache_: Cache, url: str
) -> tuple[int, str | None]:
    """Take the matrix in if it changed: the techniques now kept, and the ETag
    to remember once the caller has committed them."""
    count = int(await session.scalar(select(func.count()).select_from(AttackTechniqueRow)) or 0)
    headers = {}
    etag = await cache_.get_json(_ETAG_KEY)
    if count and isinstance(etag, str):
        headers["If-None-Match"] = etag
    response = await client.get(url, headers=headers)
    if response.status_code == httpx.codes.NOT_MODIFIED:
        return count, None
    response.raise_for_status()
    techniques = parse_stix(response.json())
    if not techniques:
        # A file of another shape: the techniques kept so far stay.
        log.warning("attack_empty", url=url)
        return count, None
    await session.execute(delete(AttackTechniqueRow))
    session.add_all(AttackTechniqueRow(id=key, name=name) for key, name in techniques.items())
    log.info("attack_refreshed", techniques=len(techniques))
    return len(techniques), response.headers.get("ETag")


async def remember(cache_: Cache, etag: str | None) -> None:
    if etag:
        await cache_.set_json(_ETAG_KEY, etag, _ETAG_TTL)


async def lookup(session: AsyncSession, ids: Sequence[str]) -> dict[str, str]:
    """The names of the techniques asked for that exist; the snapshot while
    the table is empty."""
    wanted = list(dict.fromkeys(ids))
    if not wanted:
        return {}
    rows = (
        await session.execute(
            select(AttackTechniqueRow.id, AttackTechniqueRow.name).where(
                AttackTechniqueRow.id.in_(wanted)
            )
        )
    ).all()
    found = {str(key): str(name) for key, name in rows}
    known = snapshot()
    if not found and not await session.scalar(select(func.count()).select_from(AttackTechniqueRow)):
        return {key: known[key] for key in wanted if key in known}
    # The table keeps the enterprise matrix fresh; ICS techniques (T0800 on)
    # come from the snapshot alone.
    ics = {key: known[key] for key in wanted if key.startswith("T0") and key in known}
    return {**ics, **found}
