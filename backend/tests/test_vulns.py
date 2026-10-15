# ruff: noqa: F811  (the fixtures are imported from the other tests)
"""The reference bases: the CISA KEV catalogue and BDU entries, read and looked up."""

from datetime import UTC, date, datetime

import pytest

from radar.vulns.kev import parse_catalog
from radar.vulns.lookup import _names, bdu_reference
from tests.test_accounts_api import api, database  # noqa: F401

# The lines ingest/bdu.py writes for one entry, from a real one.
BDU_TEXT = (
    "Уязвимость Citrix NetScaler ADC связана с выходом операции за границы буфера.\n"
    "Уязвимое ПО: Citrix NetScaler ADC до 14.1-47.48.\n"
    "Уровень опасности: Критический уровень опасности (базовая оценка CVSS 3.1 составляет 9).\n"
    "CVSS 3.1: AV:N/AC:H/PR:N/UI:N/S:C/C:H/I:H/A:H\n"
    "Идентификаторы: CVE: CVE-2026-88772.\n"
    "Эксплойт: существует в открытом доступе.\n"
    "Используется в атаках.\n"
    "Статус: подтверждена производителем.\n"
    "Способ устранения: обновление программного обеспечения."
)


def test_the_catalogue_is_read_and_a_broken_entry_is_skipped() -> None:
    raw = {
        "vulnerabilities": [
            {
                "cveID": "cve-2026-88772",
                "vendorProject": "Citrix",
                "product": "NetScaler ADC",
                "vulnerabilityName": "Citrix NetScaler Buffer Overflow",
                "dateAdded": "2026-09-27",
                "knownRansomwareCampaignUse": "Known",
                "shortDescription": "Out-of-bounds write.",
                "requiredAction": "Apply mitigations.",
            },
            {"cveID": "CVE-2026-1", "dateAdded": "not a date"},
        ]
    }

    [entry] = parse_catalog(raw)

    assert entry.cve_id == "CVE-2026-88772"
    assert entry.date_added == date(2026, 9, 27)
    assert entry.ransomware is True


def test_a_bdu_entry_gives_its_exploit_attacks_score_and_vector() -> None:
    reference = bdu_reference("CVE-2026-88772", "https://bdu.fstec.ru/vul/2026-15497", BDU_TEXT)

    assert reference.bdu_id == "BDU:2026-15497"
    assert reference.bdu_exploit == "существует в открытом доступе"
    assert reference.bdu_in_attacks is True
    assert reference.bdu_cvss == "9"
    assert reference.bdu_vector == "AV:N/AC:H/PR:N/UI:N/S:C/C:H/I:H/A:H"
    assert reference.bdu_fix == "обновление программного обеспечения"


@pytest.mark.integration
async def test_a_cve_is_found_in_the_catalogue_and_in_the_bdu(api: str) -> None:
    from radar.db import session_scope
    from radar.db.models import KnownExploitedVulnerability, Source
    from radar.store.articles import NewArticle, insert_new
    from radar.text import content_hash
    from radar.vulns.lookup import lookup

    async with session_scope() as session:
        # The catalogue is not cleared between tests; merge keeps the run repeatable.
        await session.merge(
            KnownExploitedVulnerability(
                cve_id="CVE-2026-88772",
                date_added=date(2026, 9, 27),
                ransomware=False,
                due_date=date(2026, 10, 18),
                cwes=["CWE-787"],
            )
        )
        source = Source(
            slug="bdu-test",
            name="БДУ ФСТЭК",
            feed_url="https://bdu.fstec.ru/ubi/vul/test/rss",
            category="regulator",
        )
        session.add(source)
        await session.flush()
        await insert_new(
            session,
            source.id,
            [
                NewArticle(
                    url="https://bdu.fstec.ru/vul/2026-15497",
                    title="Уязвимость Citrix NetScaler ADC",
                    summary="Уязвимость Citrix NetScaler ADC.",
                    content=BDU_TEXT,
                    author=None,
                    tags=(),
                    language="ru",
                    published_at=datetime(2026, 9, 28, tzinfo=UTC),
                    content_hash=content_hash("bdu", BDU_TEXT),
                )
            ],
        )

    async with session_scope() as session:
        known, unknown = await lookup(session, ["CVE-2026-88772", "CVE-2026-11111"])

    assert known.kev_added == date(2026, 9, 27)
    assert known.kev_due == date(2026, 10, 18)
    assert known.kev_cwes == ("CWE-787",)
    assert known.bdu_id == "BDU:2026-15497"
    assert known.bdu_in_attacks is True
    assert unknown.found is False


@pytest.mark.integration
async def test_every_id_of_a_roundup_is_looked_up(api: str) -> None:
    """A "trending vulnerabilities" post names dozens of CVEs; the last one is
    checked like the first, in the catalogue and in the BDU."""
    from radar.db import session_scope
    from radar.db.models import KnownExploitedVulnerability, Source
    from radar.store.articles import NewArticle, insert_new
    from radar.text import content_hash
    from radar.vulns.lookup import lookup

    ids = [f"CVE-2026-{70000 + number}" for number in range(40)]
    last = ids[-1]
    text = BDU_TEXT.replace("CVE-2026-88772", last)
    async with session_scope() as session:
        await session.merge(
            KnownExploitedVulnerability(
                cve_id=last, date_added=date(2026, 9, 27), ransomware=False, cwes=[]
            )
        )
        source = Source(
            slug="bdu-roundup-test",
            name="БДУ ФСТЭК",
            feed_url="https://bdu.fstec.ru/ubi/vul/roundup/rss",
            category="regulator",
        )
        session.add(source)
        await session.flush()
        await insert_new(
            session,
            source.id,
            [
                NewArticle(
                    url="https://bdu.fstec.ru/vul/2026-15498",
                    title="Уязвимость Citrix NetScaler ADC",
                    summary="Уязвимость Citrix NetScaler ADC.",
                    content=text,
                    author=None,
                    tags=(),
                    language="ru",
                    published_at=datetime(2026, 9, 28, tzinfo=UTC),
                    content_hash=content_hash("bdu", text),
                )
            ],
        )

    async with session_scope() as session:
        references = await lookup(session, ids)

    assert [reference.id for reference in references] == ids
    assert references[-1].kev_added == date(2026, 9, 27)
    assert references[-1].bdu_id == "BDU:2026-15498"
    assert not any(reference.found for reference in references[:-1])


def test_a_cve_is_not_found_inside_a_longer_one() -> None:
    assert _names("Идентификаторы: CVE: CVE-2024-1234.", "CVE-2024-1234")
    assert not _names("Идентификаторы: CVE: CVE-2024-12345.", "CVE-2024-1234")


async def test_attack_techniques_come_from_the_snapshot_then_from_mitre(api: str) -> None:
    import httpx
    from sqlalchemy import delete

    from radar.cache import get_cache
    from radar.db import session_scope
    from radar.db.models import AttackTechniqueRow
    from radar.vulns import attack

    async with session_scope() as session:
        await session.execute(delete(AttackTechniqueRow))
    # Nothing loaded yet: the snapshot in the package answers.
    async with session_scope() as session:
        assert await attack.lookup(session, ["T1566", "T9999"]) == {"T1566": "Phishing"}

    bundle = {
        "objects": [
            {
                "type": "attack-pattern",
                "name": "Phishing (renamed)",
                "external_references": [{"source_name": "mitre-attack", "external_id": "T1566"}],
            }
        ]
    }

    def mitre(request: httpx.Request) -> httpx.Response:
        if request.headers.get("if-none-match") == '"v1"':
            return httpx.Response(304)
        return httpx.Response(200, json=bundle, headers={"ETag": '"v1"'})

    url = "https://mitre.example/enterprise-attack.json"
    async with httpx.AsyncClient(transport=httpx.MockTransport(mitre)) as client:
        async with session_scope() as session:
            kept, etag = await attack.refresh(session, client, get_cache(), url)
        await attack.remember(get_cache(), etag)
        async with session_scope() as session:
            again, unchanged = await attack.refresh(session, client, get_cache(), url)

    assert (kept, etag, again, unchanged) == (1, '"v1"', 1, None)
    # Loaded: the table answers, and only for what it has.
    async with session_scope() as session:
        assert await attack.lookup(session, ["T1566", "T1003"]) == {"T1566": "Phishing (renamed)"}
        # The table keeps the enterprise matrix; ICS comes from the snapshot.
        assert await attack.lookup(session, ["T0817", "T1003"]) == {"T0817": "Drive-by Compromise"}
        await session.execute(delete(AttackTechniqueRow))
