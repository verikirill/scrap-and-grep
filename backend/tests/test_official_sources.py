"""Official sources: the national CA for their hosts, BDU's vulnerability pages,
the trending vulnerabilities of Positive Technologies."""

import json
from datetime import UTC, date, datetime
from importlib.resources import files
from pathlib import Path

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from pydantic import ValidationError

from radar.config import Settings
from radar.ingest import bdu
from radar.ingest.fetch import Ladder
from radar.ingest.net import RUSSIAN_CA_BUNDLE, TrustByHost, trusts_russian_ca
from radar.ingest.pages import MarkupChanged, page_text
from radar.ingest.ptsecurity import fetch_trending, parse_trending, to_article
from tests.test_telegram import offline  # noqa: F401  (fixture)

PT_PAGE = (Path(__file__).parent / "fixtures" / "ptsecurity" / "trending.html").read_text("utf-8")
PT_URL = "https://ptsecurity.com/research/trending-vulnerabilities/"
NOW = datetime(2026, 10, 2, 12, tzinfo=UTC)
# The root and the two intermediates as the Ministry of Digital Development
# publishes them (backend/src/radar/ingest/certs/russian_trusted_ca.pem).
ROOT_SHA256 = "d26d2d0231b7c39f92cc738512ba54103519e4405d68b5bd703e9788ca8ecf31"
INTERMEDIATE_SHA256 = {
    "bbbde2103e790b999ec62bd03cf625a5a2e7c316e10afe6a490eedead8b3fd9b",
    "2155785036c900dbb5f1bb2a1569c80c55595bd6bf94867a29bbddbc7d88a3f2",
}

MODEL = {
    "vul_desc": "Уязвимость веб-интерфейса шлюза телемеханики связана с обходом аутентификации. "
    "Эксплуатация уязвимости может позволить нарушителю выполнить произвольный код",
    "vul_critu": "Высокий уровень опасности (базовая оценка CVSS 2.0 составляет 9)\r\n"
    "Критический уровень опасности (базовая оценка CVSS 3.1 составляет 9,8)",
    "vul_datv": "2026-09-26",
    "vul_expl": 2,
    "vul_incident": 1,
    "vul_state": 1,
    "vul_elimination": 1,
    "vul_vmer": "Использование рекомендаций производителя:\r\nhttps://vendor.example/advisory",
    "versions": [
        {
            "ver_name": "до 2.4.1",
            "soft": {"sft_name": "Шлюз ШТ-2", "vendor": {"vnd_name": "Энергософт"}},
        }
    ],
    "softs": ["Шлюз ШТ-2"],
    "cwes": [{"cwe_idn": 287, "cwe_name": "Неправильная аутентификация"}],
    "cvsses3": ['CVSS 3.1: <a href="/calc3?bs=AV">AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H</a>'],
    "idvals": ['CVE: <a href="https://nvd.example/CVE-2026-99001">CVE-2026-99001</a>'],
}


def bdu_page(model: dict[str, object]) -> str:
    """A BDU vulnerability page: Vue templates, and the data in a script."""
    return (
        "<html><body><table><tr><td>Описание уязвимости</td><td>{{v_model.vul_desc}}</td></tr>"
        "</table><script>const v_noInformation = ref('Данные уточняются');\n"
        f"const v_model = reactive({json.dumps(model, ensure_ascii=False)});\n"
        "const v_components = reactive({select: null});</script></body></html>"
    )


def test_the_bundled_national_ca_is_the_published_root_and_its_intermediates() -> None:
    pem = files("radar.ingest").joinpath(RUSSIAN_CA_BUNDLE).read_bytes()
    root, *intermediates = x509.load_pem_x509_certificates(pem)

    assert root.fingerprint(hashes.SHA256()).hex() == ROOT_SHA256
    assert {
        cert.fingerprint(hashes.SHA256()).hex() for cert in intermediates
    } == INTERMEDIATE_SHA256
    for certificate in intermediates:
        certificate.verify_directly_issued_by(root)


@pytest.mark.parametrize(
    ("host", "trusted"),
    [
        ("bdu.fstec.ru", True),
        ("PTSecurity.com.", True),
        ("www.ptsecurity.com", True),
        # Only BDU on the regulator's domain.
        ("fstec.ru", False),
        ("www.fstec.ru", False),
        ("evilfstec.ru", False),
        ("fstec.ru.example.org", False),
        ("example.org", False),
    ],
)
def test_the_national_ca_is_trusted_only_for_the_listed_domains(host: str, trusted: bool) -> None:
    assert trusts_russian_ca(host) is trusted


@pytest.mark.parametrize("hosts", [["ru"], [""], ["."], ["bdu..fstec.ru"]])
def test_a_host_list_that_would_trust_the_ca_too_widely_is_refused(hosts: list[str]) -> None:
    with pytest.raises(ValidationError):
        Settings(russian_ca_hosts=hosts)


def test_host_names_for_the_national_ca_are_normalised() -> None:
    assert Settings(russian_ca_hosts=[" BDU.fstec.ru. "]).russian_ca_hosts == ["bdu.fstec.ru"]


async def test_a_request_goes_through_the_pool_that_trusts_its_host() -> None:
    used: list[str] = []

    def pool(name: str) -> httpx.MockTransport:
        def handle(_: httpx.Request) -> httpx.Response:
            used.append(name)
            return httpx.Response(200)

        return httpx.MockTransport(handle)

    transport = TrustByHost(usual=pool("usual"), national=pool("national"))
    async with httpx.AsyncClient(transport=transport) as client:
        # A pinned request goes to the address; TLS checks the name in SNI.
        await client.get("https://95.173.157.16/vul", extensions={"sni_hostname": "bdu.fstec.ru"})
        await client.get("https://93.184.215.14/", extensions={"sni_hostname": "example.org"})
        await client.get("https://ptsecurity.com/research/")

    assert used == ["national", "usual", "national"]


def test_a_bdu_page_is_read_from_its_data_not_its_templates() -> None:
    url = "https://bdu.fstec.ru/vul/2026-99001"
    text = page_text(url, bdu_page(MODEL))

    assert text is not None
    assert "{{" not in text
    lines = text.splitlines()
    assert lines[0].startswith("Уязвимость веб-интерфейса шлюза телемеханики")
    # BDU leaves the full stop off; the text puts it back.
    assert lines[0].endswith("произвольный код.")
    assert "Уязвимое ПО: Энергософт Шлюз ШТ-2 до 2.4.1." in lines
    assert "CVSS 3.1: AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H" in lines
    assert "Тип ошибки: CWE-287, Неправильная аутентификация." in lines
    assert "Идентификаторы: CVE: CVE-2026-99001." in lines
    assert "Эксплойт: существует в открытом доступе." in lines
    assert "Используется в атаках." in lines
    assert "Дата выявления: 26.09.2026." in lines
    assert lines[-1].endswith("https://vendor.example/advisory")


def test_a_bdu_page_without_its_data_gives_no_text_rather_than_menus() -> None:
    broken = bdu_page(MODEL).replace("reactive(", "reactive(oops")

    assert page_text("https://bdu.fstec.ru/vul/2026-99001", broken) is None
    assert page_text("https://bdu.fstec.ru/vul/2026-99001", bdu_page({"vul_desc": ""})) is None
    # Only a vulnerability's own page is read this way.
    assert not bdu.is_vulnerability_page("https://bdu.fstec.ru/vul/danger")
    assert not bdu.is_vulnerability_page("https://evil.example/vul/2026-99001")


def test_odd_values_in_bdu_data_lose_their_line_not_the_text() -> None:
    odd = {
        **MODEL,
        "vul_incident": True,
        "vul_expl": 1.0,
        "versions": ["строка вместо объекта", {"soft": "тоже строка"}],
        "softs": ["Шлюз ШТ-2"],
        "cwes": [287],
        "cvsses3": "строка",
        "vul_datv": 20260926,
    }
    spaced = bdu_page(MODEL).replace("reactive({", "reactive(\n  {")
    deep = bdu_page(MODEL).replace("reactive({", "reactive(" + "[" * 100_000)

    text = page_text("https://bdu.fstec.ru/vul/2026-99001", bdu_page(odd))

    assert text is not None
    lines = text.splitlines()
    assert "Используется в атаках." in lines
    assert "Эксплойт: существует." in lines
    assert "Уязвимое ПО: Шлюз ШТ-2." in lines
    assert not any(line.startswith(("Тип ошибки", "Дата выявления", "CVSS")) for line in lines)
    assert page_text("https://bdu.fstec.ru/vul/2026-99001", spaced) is not None
    assert page_text("https://bdu.fstec.ru/vul/2026-99001", deep) is None


def test_trending_vulnerabilities_are_read_from_the_cards() -> None:
    first, second, unrated = parse_trending(PT_PAGE, PT_URL)

    assert first.id == "CVE-2026-99001"
    assert first.url == f"{PT_URL}CVE-2026-99001"
    assert (first.rating, first.score) == ("Критический", "9.8")
    assert first.vector == "AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    assert (first.vendor, first.product) == ("Энергософт", "Шлюз телемеханики ШТ-2")
    assert first.since == date(2026, 9, 24)
    # The vendor is not repeated when the product already names it.
    assert second.software == "Microsoft Windows"
    assert (unrated.rating, unrated.score, unrated.software) == (
        "Без рейтинга",
        None,
        "Мониторинг-Про",
    )


def test_a_card_address_stays_on_pt_and_is_its_own() -> None:
    page = (
        PT_PAGE.replace('href="CVE-2026-99001"', 'href="javascript:alert(1)"')
        .replace('href="CVE-2026-99002"', 'href="https://evil.example/CVE-2026-99002"')
        .replace("Высокий<!-- --> – <!-- -->7.8", "Средне-высокий<!-- --> – <!-- -->7.8")
    )

    first, second, unrated = parse_trending(page, PT_URL.rstrip("/"))

    assert first.url == f"{PT_URL}CVE-2026-99001"
    assert second.url == f"{PT_URL}CVE-2026-99002"
    # "BDU:" is the identifier, not a scheme.
    assert unrated.url == f"{PT_URL}BDU:2026-99003"
    # A hyphen inside the rating is not the dash before the score.
    assert (second.rating, second.score) == ("Средне-высокий", "7.8")


def test_a_trending_vulnerability_becomes_an_article_on_the_day_it_was_marked() -> None:
    article = to_article(parse_trending(PT_PAGE, PT_URL)[0], NOW)

    assert (
        article.title == "Трендовая уязвимость CVE-2026-99001 в Энергософт Шлюз телемеханики ШТ-2"
    )
    assert article.url == "https://ptsecurity.com/research/trending-vulnerabilities/CVE-2026-99001"
    # Midnight in Moscow.
    assert article.published_at == datetime(2026, 9, 23, 21, tzinfo=UTC)
    assert article.tags == ("трендовая уязвимость", "CVE-2026-99001", "Энергософт")
    assert article.content is not None
    assert "Уровень опасности: Критический, CVSS 9.8." in article.content
    assert article.summary.startswith("Уязвимость в веб-интерфейсе контроллера SCADA-шлюза")


def test_a_page_whose_cards_cannot_be_read_is_an_error() -> None:
    undated = PT_PAGE.replace("Стала трендовой", "Добавлена")

    with pytest.raises(MarkupChanged):
        parse_trending(undated, PT_URL)
    with pytest.raises(MarkupChanged):
        parse_trending("<html><body><p>Технические работы</p></body></html>", PT_URL)


async def test_an_unchanged_trending_page_is_not_read_again(offline: None) -> None:  # noqa: F811
    def handle(request: httpx.Request) -> httpx.Response:
        if request.headers.get("if-none-match") == '"v1"':
            return httpx.Response(304)
        return httpx.Response(200, text=PT_PAGE, headers={"etag": '"v1"'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        ladder = Ladder(http)
        first = await fetch_trending(ladder, PT_URL, etag=None, last_modified=None)
        again = await fetch_trending(ladder, PT_URL, etag=first.etag, last_modified=None)

    assert (first.status, len(first.articles), first.etag) == ("ok", 3, '"v1"')
    assert again.status == "not_modified"
