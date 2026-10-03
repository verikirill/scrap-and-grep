# ruff: noqa: F811  (the fixtures are imported from the other tests)
"""The local copies of NVD, EPSS and Exploit-DB: read, kept and looked up.

The NVD records are two real ones from NVD's feed of October 3, 2026, cut
down; the EPSS and Exploit-DB lines are copied from the real files.
"""

import gzip
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from radar.cards import exploit_evidence
from radar.domain import VulnerabilityReference
from radar.vulns.epss import parse_scores
from radar.vulns.exploitdb import parse_index
from radar.vulns.nvd import parse_page
from tests.test_accounts_api import api, database  # noqa: F401

PAGE: dict[str, Any] = json.loads(
    (Path(__file__).parent / "fixtures" / "nvd" / "changed.json").read_text(encoding="utf-8")
)
EPSS = (
    "#model_version:v2026.06.15,score_date:2026-10-03T12:00:21Z\n"
    "cve,epss,percentile\n"
    "CVE-2018-7602,0.94431,0.99961\n"
    "CVE-2009-10005,0.01377,0.79771\n"
    "CVE-2026-0001,not a number,0.1\n"
)
EXPLOITDB = (
    "id,file,description,date_published,author,type,platform,port,date_added,date_updated,"
    "verified,codes,tags,aliases,screenshot_url,application_url,source_url\n"
    "44542,exploits/php/webapps/44542.txt,"
    "\"Drupal < 7.58 - 'Drupalgeddon3' (Authenticated) Remote Code (Metasploit)\","
    "2018-04-30,SixP4ck3r,webapps,php,,2018-04-30,2018-04-30,1,CVE-2018-7602,,,,,\n"
    "44557,exploits/php/webapps/44557.rb,"
    "\"Drupal < 7.58 - 'Drupalgeddon3' (Authenticated) Remote Code Execution (PoC)\","
    '2018-04-30,"Blaklis",webapps,php,,2018-04-30,2018-04-30,0,'
    "CVE-2018-7602;CVE-2018-7600,,,,,\n"
    '16929,exploits/aix/dos/16929.rb,"AIX Calendar Manager - Buffer Overflow",'
    "2010-11-11,Metasploit,dos,aix,,2010-11-11,2011-03-06,1,OSVDB-58726,,,,,\n"
)


def test_an_analysed_record_gives_its_score_weakness_products_and_exploit() -> None:
    drupal, appliance = parse_page(PAGE)

    assert drupal.cve_id == "CVE-2018-7602"
    assert (drupal.cvss_version, drupal.cvss_score, drupal.severity) == ("3.1", "9.8", "critical")
    assert drupal.cvss_vector == "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    assert drupal.cwes == ("CWE-94",)
    assert drupal.exploitation == "active"
    assert drupal.exploit_links[0] == "https://www.exploit-db.com/exploits/44542/"
    assert drupal.patch_links == ("https://www.drupal.org/sa-core-2018-004",)
    assert drupal.products == ("drupal drupal", "debian debian linux")
    assert drupal.published == date(2018, 7, 19)
    # Not analysed yet: the CNA's 4.0 score, its product list, SSVC says PoC.
    assert appliance.status == "Deferred"
    assert (appliance.cvss_version, appliance.cvss_score) == ("4.0", "8.7")
    assert (
        appliance.cvss_vector == "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N"
    )
    assert appliance.exploitation == "poc"
    assert appliance.products == ("ContentKeeper Technologies Web Appliance",)


def test_a_record_without_an_id_or_of_another_shape_is_skipped() -> None:
    page = {"vulnerabilities": [{"cve": {"id": "not-a-cve"}}, {"cve": None}, "junk"]}

    assert parse_page(page) == []


def test_epss_scores_are_read_with_their_date_gzipped_or_not() -> None:
    plain = parse_scores(EPSS.encode())
    zipped = parse_scores(gzip.compress(EPSS.encode()))

    assert plain == zipped
    assert [entry.cve_id for entry in plain] == ["CVE-2018-7602", "CVE-2009-10005"]
    assert plain[0].score == pytest.approx(0.94431)
    assert plain[0].scored_on == date(2026, 10, 3)


def test_an_exploit_is_kept_once_per_cve_it_names_and_one_without_a_cve_is_not() -> None:
    entries = parse_index(EXPLOITDB.encode())

    assert sorted((entry.cve_id, entry.edb_id) for entry in entries) == [
        ("CVE-2018-7600", 44557),
        ("CVE-2018-7602", 44542),
        ("CVE-2018-7602", 44557),
    ]
    verified = {entry.edb_id: entry.verified for entry in entries}
    assert verified == {44542: True, 44557: False}


def test_the_reference_text_gives_the_card_its_exploit_sign() -> None:
    """The check of a card reads the exploit from the evidence, the reference
    text included: the words must say what the bases say, and EPSS alone,
    a probability, must say nothing."""

    def sign(**facts: Any) -> str:
        return exploit_evidence(VulnerabilityReference(id="CVE-2018-7602", **facts).text())

    assert sign(nvd_exploitation="active") == "in_the_wild"
    assert sign(nvd_exploitation="poc") == "public"
    assert sign(exploits=("EDB-44542",)) == "public"
    assert sign(nvd_exploit_links=("https://www.exploit-db.com/exploits/44542/",)) == "public"
    assert sign(epss=0.94, epss_percentile=0.999, nvd_cvss="9.8") == "unknown"
    assert VulnerabilityReference(id="CVE-2018-7602", epss=0.01).found


def _nvd(pages: list[dict[str, Any]], seen: list[httpx.Request]) -> httpx.MockTransport:
    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        cve = request.url.params.get("cveId")
        if cve is not None:
            found = [item for item in PAGE["vulnerabilities"] if item["cve"]["id"] == cve]
            return httpx.Response(200, json={"totalResults": len(found), "vulnerabilities": found})
        index = int(request.url.params["startIndex"])
        return httpx.Response(200, json=pages[index])

    return httpx.MockTransport(answer)


@pytest.mark.integration
async def test_nvd_changes_are_paged_and_the_window_moves_on(api: str) -> None:
    from sqlalchemy import delete, select

    from radar.cache import get_cache
    from radar.db import session_scope
    from radar.db.models import NvdVulnerability
    from radar.vulns import nvd

    first, second = PAGE["vulnerabilities"]
    pages = [
        {"resultsPerPage": 1, "startIndex": 0, "totalResults": 2, "vulnerabilities": [first]},
        {"resultsPerPage": 1, "startIndex": 1, "totalResults": 2, "vulnerabilities": [second]},
    ]
    seen: list[httpx.Request] = []
    now = datetime(2026, 10, 3, 16, 0, tzinfo=UTC)
    url = "https://nvd.example/rest/json/cves/2.0"
    await get_cache().set_json("nvd:cursor", None, 1)
    async with session_scope() as session:
        await session.execute(delete(NvdVulnerability))
    async with httpx.AsyncClient(transport=_nvd(pages, seen)) as client:
        async with session_scope() as session:
            taken, cursor = await nvd.refresh_changed(
                session, client, get_cache(), url, "a-key", pause=0, now=now
            )
        await nvd.remember(get_cache(), cursor)
        async with session_scope() as session:
            await nvd.refresh_changed(session, client, get_cache(), url, pause=0, now=now)

    assert taken == 2
    assert [request.url.params["startIndex"] for request in seen] == ["0", "1", "0", "1"]
    # The first round looks a day back, the next from where the first ended.
    assert seen[0].url.params["lastModStartDate"] == "2026-10-02T16:00:00.000+00:00"
    assert seen[2].url.params["lastModStartDate"] == "2026-10-03T16:00:00.000+00:00"
    assert seen[0].headers["apiKey"] == "a-key"
    assert "apiKey" not in seen[2].headers
    async with session_scope() as session:
        kept = {row.cve_id: row for row in await session.scalars(select(NvdVulnerability))}
    assert set(kept) == {"CVE-2018-7602", "CVE-2009-10005"}
    assert kept["CVE-2018-7602"].cwes == ["CWE-94"]


@pytest.mark.integration
async def test_cves_the_articles_name_are_asked_for_and_an_unknown_one_is_marked(
    api: str,
) -> None:
    from sqlalchemy import delete, select

    from radar.db import session_scope
    from radar.db.models import NvdVulnerability, Source
    from radar.store.articles import NewArticle, insert_new
    from radar.text import content_hash
    from radar.vulns import nvd

    now = datetime(2026, 10, 3, 16, 0, tzinfo=UTC)
    text = "Drupalgeddon 3 (cve-2018-7602) снова в атаках, а CVE-2026-99999 пока не описана."
    async with session_scope() as session:
        await session.execute(delete(NvdVulnerability))
        source = Source(
            slug="nvd-test", name="Тест", feed_url="https://news.example/rss", category="media"
        )
        session.add(source)
        await session.flush()
        await insert_new(
            session,
            source.id,
            [
                NewArticle(
                    url="https://news.example/drupal",
                    title="Drupalgeddon снова",
                    summary=text,
                    content=text,
                    author=None,
                    tags=(),
                    language="ru",
                    published_at=datetime(2026, 10, 2, tzinfo=UTC),
                    content_hash=content_hash("nvd", text),
                )
            ],
        )

    seen: list[httpx.Request] = []
    url = "https://nvd.example/rest/json/cves/2.0"
    async with httpx.AsyncClient(transport=_nvd([], seen)) as client:
        async with session_scope() as session:
            asked = await nvd.backfill(session, client, url, pause=0, now=now)
        async with session_scope() as session:
            # Both kept now: the unknown one waits a few days before it is asked again.
            again = await nvd.backfill(session, client, url, pause=0, now=now)

    assert (asked, again) == (2, 0)
    assert sorted(request.url.params["cveId"] for request in seen) == [
        "CVE-2018-7602",
        "CVE-2026-99999",
    ]
    async with session_scope() as session:
        rows = {row.cve_id: row.status for row in await session.scalars(select(NvdVulnerability))}
        later = await nvd.named_but_missing(session, datetime(2026, 10, 7, tzinfo=UTC), 10)
    assert rows == {"CVE-2018-7602": "Analyzed", "CVE-2026-99999": nvd.ABSENT}
    assert later == ["CVE-2026-99999"]


@pytest.mark.integration
async def test_the_lookup_answers_from_the_three_copies(api: str) -> None:
    from sqlalchemy import delete

    from radar.cache import get_cache
    from radar.db import session_scope
    from radar.db.models import EpssScore, NvdVulnerability, PublicExploit
    from radar.vulns import epss, exploitdb, nvd
    from radar.vulns.lookup import lookup

    def files(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/current.csv.gz":
            return httpx.Response(302, headers={"Location": "scores-2026-10-03.csv.gz"})
        if request.url.host == "epss.example":
            if request.headers.get("if-modified-since") == "Sat, 03 Oct 2026 13:30:21 GMT":
                return httpx.Response(304)
            headers = {"Last-Modified": "Sat, 03 Oct 2026 13:30:21 GMT"}
            return httpx.Response(200, content=gzip.compress(EPSS.encode()), headers=headers)
        return httpx.Response(200, content=EXPLOITDB.encode(), headers={"ETag": '"edb1"'})

    async with session_scope() as session:
        for table in (NvdVulnerability, EpssScore, PublicExploit):
            await session.execute(delete(table))
        await nvd.store(session, parse_page(PAGE))
    await get_cache().set_json("epss:last-modified", None, 1)
    async with httpx.AsyncClient(transport=httpx.MockTransport(files)) as client:
        async with session_scope() as session:
            scores, modified = await epss.refresh(
                session, client, get_cache(), "https://epss.example/current.csv.gz"
            )
        await epss.remember(get_cache(), modified)
        async with session_scope() as session:
            unchanged = await epss.refresh(
                session, client, get_cache(), "https://epss.example/current.csv.gz"
            )
            exploits, etag = await exploitdb.refresh(
                session, client, get_cache(), "https://edb.example/files_exploits.csv"
            )

    assert (scores, unchanged, exploits, etag) == (2, (2, None), 3, '"edb1"')
    async with session_scope() as session:
        drupal, appliance, unknown = await lookup(
            session, ["CVE-2018-7602", "CVE-2009-10005", "CVE-2026-11111"]
        )

    assert drupal.nvd_cvss == "9.8"
    assert drupal.nvd_cwes == ("CWE-94",)
    assert drupal.nvd_exploitation == "active"
    assert drupal.nvd_patch is True
    assert drupal.epss == pytest.approx(0.94431)
    # The verified exploit first.
    assert drupal.exploits == ("EDB-44542", "EDB-44557")
    assert appliance.nvd_exploitation == "poc"
    assert appliance.exploits == ()
    assert unknown.found is False
    assert "EPSS 94,4%" in drupal.text()
