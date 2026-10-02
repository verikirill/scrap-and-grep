"""What the reference bases say of a vulnerability, by its CVE or BDU id.

The CISA KEV catalogue answers whether it is exploited in the wild. The BDU
of FSTEC answers in Russian: an exploit in the open, use in attacks, the CVSS
score and vector, the fix. BDU entries are articles of the BDU sources,
written field by field by ingest/bdu.py; their lines are read back here.
"""

import re
from collections.abc import Sequence

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from radar.cards import identifiers
from radar.db.models import Article, KnownExploitedVulnerability, Source
from radar.domain import VulnerabilityReference
from radar.text import truncate

# Enough for one card: a roundup of thirty CVEs is not looked up whole.
MAX_IDS = 6
_BDU_PAGE_RE = re.compile(r"bdu\.fstec\.ru/vul/(\d{4}-\d{5})")
_EXPLOIT_RE = re.compile(r"^Эксплойт: (.+?)\.$", re.MULTILINE)
_SCORE_RE = re.compile(r"базовая оценка CVSS 3\.\d составляет (\d+(?:[.,]\d+)?)")
_VECTOR_RE = re.compile(r"^CVSS 3\.\d: (\S+)$", re.MULTILINE)
_FIX_RE = re.compile(r"^Способ устранения: (.+?)\.$", re.MULTILINE)


def _names(text: str, identifier: str) -> bool:
    """The id itself, not a longer one it starts: CVE-2024-1234 is not CVE-2024-12345."""
    return re.search(rf"{re.escape(identifier)}(?!\d)", text) is not None


def bdu_reference(identifier: str, url: str, text: str) -> VulnerabilityReference:
    """The facts of one BDU entry, from the lines ingest/bdu.py writes."""
    page = _BDU_PAGE_RE.search(url)
    exploit = _EXPLOIT_RE.search(text)
    score = _SCORE_RE.search(text)
    vector = _VECTOR_RE.search(text)
    fix = _FIX_RE.search(text)
    return VulnerabilityReference(
        id=identifier,
        bdu_id=f"BDU:{page.group(1)}" if page else "",
        bdu_exploit=exploit.group(1) if exploit else "",
        bdu_in_attacks="\nИспользуется в атаках." in f"\n{text}",
        bdu_cvss=score.group(1).replace(",", ".") if score else "",
        bdu_vector=vector.group(1) if vector else "",
        bdu_fix=truncate(fix.group(1), 120) if fix else "",
    )


async def lookup(session: AsyncSession, values: Sequence[str]) -> list[VulnerabilityReference]:
    """One reference per id, found or not, in the order asked."""
    ids = identifiers(" ".join(values))[:MAX_IDS]
    if not ids:
        return []
    cves = [value for value in ids if value.startswith("CVE-")]
    kev = {
        row.cve_id: row
        for row in await session.scalars(
            select(KnownExploitedVulnerability).where(KnownExploitedVulnerability.cve_id.in_(cves))
        )
    }
    # A BDU entry names its CVEs in its text; a BDU id is in its address.
    wanted = [Article.content.contains(value) for value in cves] + [
        Article.url.contains(value.removeprefix("BDU:"))
        for value in ids
        if value.startswith("BDU:")
    ]
    entries = (
        await session.execute(
            select(Article.url, Article.content)
            .join(Source, Source.id == Article.source_id)
            .where(Source.feed_url.contains("bdu.fstec.ru"), or_(*wanted))
            .order_by(Article.published_at.desc())
            .limit(MAX_IDS * 4)
        )
    ).all()
    references = []
    for value in ids:
        bdu = next(
            (
                bdu_reference(value, url, content or "")
                for url, content in entries
                if _names(content or "", value) or _names(url, value.removeprefix("BDU:"))
            ),
            VulnerabilityReference(id=value),
        )
        known = kev.get(value)
        references.append(
            bdu.model_copy(
                update={
                    "kev_added": known.date_added if known else None,
                    "kev_ransomware": bool(known and known.ransomware),
                    "kev_due": known.due_date if known else None,
                    "kev_cwes": tuple(known.cwes) if known else (),
                }
            )
        )
    return references
