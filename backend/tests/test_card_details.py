"""The technical detail a specialist asked for at the Q&A: the attack vector,
ATT&CK techniques, indicators, CWE, the CVSS vector in words and the date
CISA wants a vulnerability fixed by."""

from datetime import date

import pytest

from radar.cards import (
    attack_rows,
    check_attack,
    check_vulnerability,
    extract_indicators,
    parse_cvss_vector,
    reference_rows,
    vulnerability_rows,
)
from radar.domain import AttackCard, AttackTechnique, VulnerabilityCard, VulnerabilityReference
from radar.vulns.attack import parse_stix, snapshot
from radar.vulns.kev import parse_catalog

SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_a_public_address_is_an_indicator_a_private_one_is_not() -> None:
    assert extract_indicators("Сервер 185.12.4.7 управлял, внутри сети 10.0.0.5.") == [
        "185.12.4[.]7"
    ]


def test_a_defanged_address_stays_defanged_once() -> None:
    assert extract_indicators("Загрузка с hxxps://evil[.]example/payload.bin") == [
        "hxxps://evil[.]example/payload.bin"
    ]


def test_an_ordinary_link_is_a_reference_not_an_indicator() -> None:
    assert extract_indicators("Бюллетень: https://vendor.example/advisory") == []


def test_a_hash_is_an_indicator() -> None:
    assert extract_indicators(f"SHA-256: {SHA256}") == [SHA256]


def test_the_same_indicator_twice_is_one() -> None:
    assert extract_indicators("C2 185.12.4.7, позже 185.12.4[.]7") == ["185.12.4[.]7"]


def test_a_defanged_domain_is_an_indicator() -> None:
    assert extract_indicators("Домен evil[.]com раздавал загрузчик.") == ["evil[.]com"]


def test_a_cvss_3_vector_reads_in_words() -> None:
    assert parse_cvss_vector("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") == [
        ("Доступ", "по сети"),
        ("Сложность", "низкая"),
        ("Права", "не нужны"),
        ("Действия пользователя", "не нужны"),
    ]


def test_a_cvss_4_vector_reads_in_words() -> None:
    vector = "CVSS:4.0/AV:L/AC:L/AT:N/PR:L/UI:A/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N"

    assert parse_cvss_vector(vector) == [
        ("Доступ", "локально"),
        ("Сложность", "низкая"),
        ("Права", "низкие"),
        ("Действия пользователя", "нужны"),
    ]


def test_a_cvss_2_vector_reads_its_access_and_complexity() -> None:
    assert parse_cvss_vector("AV:N/AC:M/Au:N/C:P/I:P/A:P") == [
        ("Доступ", "по сети"),
        ("Сложность", "средняя"),
    ]


def test_a_vector_that_is_not_one_reads_as_nothing() -> None:
    assert parse_cvss_vector("высокий") == []


KNOWN = {"T1566": "Phishing", "T1190": "Exploit Public-Facing Application"}


def test_a_technique_the_text_describes_stays_with_its_attack_name() -> None:
    card = AttackCard(techniques=(AttackTechnique(id="T1566", name="Фишинг"),))

    checked, removed = check_attack(card, "Злоумышленники рассылали фишинг сотрудникам.", KNOWN)

    assert checked.techniques == (AttackTechnique(id="T1566", name="Phishing"),)
    assert removed == []


def test_a_technique_attack_does_not_know_is_taken_out() -> None:
    card = AttackCard(techniques=(AttackTechnique(id="T9999", name="Фишинг"),))

    checked, removed = check_attack(card, "Злоумышленники рассылали фишинг.", KNOWN)

    assert checked.techniques == ()
    assert removed == ["Техники ATT&CK"]


def test_a_technique_the_text_does_not_describe_is_taken_out() -> None:
    card = AttackCard(techniques=(AttackTechnique(id="T1190", name="Эксплуатация"),))

    checked, removed = check_attack(card, "Злоумышленники рассылали письма.", KNOWN)

    assert checked.techniques == ()
    assert removed == ["Техники ATT&CK"]


def test_without_the_reference_a_technique_needs_its_id_in_the_text() -> None:
    card = AttackCard(techniques=(AttackTechnique(id="T1566", name="Фишинг"),))

    kept, _ = check_attack(card, "Использована техника T1566.", None)
    lost, _ = check_attack(card, "Рассылали фишинг.", None)

    assert kept.techniques == card.techniques
    assert lost.techniques == ()


def test_indicators_come_from_the_text_and_the_models_own_need_it() -> None:
    card = AttackCard(indicators=("203.0.113.9", "185.12.4.7"))

    checked, removed = check_attack(card, f"C2: 185.12.4.7, файл {SHA256}.", None)

    assert checked.indicators == ("185.12.4[.]7", SHA256)
    assert checked.iocs is True
    assert "Индикаторы компрометации" in removed


def test_a_cwe_the_text_does_not_name_is_taken_out() -> None:
    card = VulnerabilityCard(cwe=("CWE-79", "CWE-787"), equipment="Siemens S7-1500")

    checked, removed = check_vulnerability(card, "Ошибка CWE-787 в ПЛК Siemens S7-1500.")

    assert checked.cwe == ("CWE-787",)
    assert checked.equipment == "Siemens S7-1500"
    assert "CWE" in removed


def test_the_catalogue_gives_the_due_date_and_cwe() -> None:
    (entry,) = parse_catalog(
        {
            "vulnerabilities": [
                {
                    "cveID": "CVE-2026-1234",
                    "dateAdded": "2026-09-27",
                    "dueDate": "2026-10-18",
                    "cwes": ["CWE-787"],
                }
            ]
        }
    )

    assert entry.due_date == date(2026, 10, 18)
    assert entry.cwes == ("CWE-787",)


def test_the_due_date_is_in_the_reference_text_and_row() -> None:
    reference = VulnerabilityReference(
        id="CVE-2026-1234",
        kev_added=date(2026, 9, 27),
        kev_due=date(2026, 10, 18),
        kev_cwes=("CWE-787",),
    )

    assert "устранить до 18.10.2026" in reference.text()
    assert "CWE-787" in reference.text()
    assert "устранить до 18.10.2026" in reference_rows([reference])[0][1]


def test_a_bdu_id_the_partial_copy_lacks_is_not_called_missing() -> None:
    """The local BDU holds the entries of two feeds only: an id it lacks may
    well exist. A CVE that no base knows is still named."""
    known = VulnerabilityReference(id="BDU:2026-15497", bdu_id="BDU:2026-15497")
    lacking = VulnerabilityReference(id="BDU:2026-01678")
    unknown = VulnerabilityReference(id="CVE-2026-11111")

    [(_, row)] = reference_rows([known, lacking, unknown])

    assert "BDU:2026-01678" not in row
    assert row.startswith("BDU:2026-15497: BDU:2026-15497")
    assert row.endswith("нет в справочных базах: CVE-2026-11111")
    assert reference_rows([lacking]) == []
    assert "нет в справочных базах" not in lacking.text()


def test_the_attack_card_lists_the_new_rows() -> None:
    card = AttackCard(
        vector="фишинг",
        initial_access="вложение письма",
        affected="Microsoft Exchange 2019",
        techniques=(AttackTechnique(id="T1566", name="Phishing"),),
        indicators=("185.12.4[.]7",),
    )

    rows = dict(attack_rows(card))

    assert rows["Вектор атаки"] == "фишинг"
    assert rows["Первоначальный доступ"] == "вложение письма"
    assert rows["Затронутые продукты"] == "Microsoft Exchange 2019"
    assert rows["Техники ATT&CK"] == "T1566 Phishing"
    assert rows["Индикаторы компрометации"] == "185.12.4[.]7"


def test_the_vulnerability_card_reads_its_vector_and_ics_fields() -> None:
    card = VulnerabilityCard(
        cvss_score="9.8",
        cvss_vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        cwe=("CWE-787",),
        equipment="Siemens S7-1500",
        protocols="Profinet",
    )

    rows = dict(vulnerability_rows(card))

    assert rows["Доступ"] == "по сети"
    assert rows["CWE"] == "CWE-787"
    assert rows["Оборудование"] == "Siemens S7-1500"
    assert rows["Протоколы"] == "Profinet"


def test_an_ics_row_is_left_out_when_empty() -> None:
    rows = dict(vulnerability_rows(VulnerabilityCard()))

    assert "Оборудование" not in rows
    assert "Протоколы" not in rows


def test_the_stix_bundle_gives_techniques_and_skips_revoked_ones() -> None:
    bundle = {
        "objects": [
            {
                "type": "attack-pattern",
                "name": "Phishing",
                "external_references": [{"source_name": "mitre-attack", "external_id": "T1566"}],
            },
            {
                "type": "attack-pattern",
                "name": "Old",
                "revoked": True,
                "external_references": [{"source_name": "mitre-attack", "external_id": "T1000"}],
            },
            {"type": "malware", "name": "Not a technique"},
        ]
    }

    assert parse_stix(bundle) == {"T1566": "Phishing"}


@pytest.mark.parametrize("value", ["T1566", "T1566.001"])
def test_a_technique_id_has_the_mitre_shape(value: str) -> None:
    assert AttackTechnique(id=value, name="x").id == value


def test_a_version_of_four_numbers_is_no_address() -> None:
    assert extract_indicators("Обновите до версии 5.4.2.1, сервер 185.12.4.7.") == ["185.12.4[.]7"]


def test_a_technique_the_article_prints_counts_without_the_model() -> None:
    known = {**KNOWN, "T0817": "Drive-by Compromise"}
    source = "Вход через T1190, затем T0817 на станции оператора; сканер T1000 ни при чём."

    checked, removed = check_attack(AttackCard(), source, known)

    assert checked.techniques == (
        AttackTechnique(id="T1190", name="Exploit Public-Facing Application"),
        AttackTechnique(id="T0817", name="Drive-by Compromise"),
    )
    assert removed == []


def test_an_id_in_the_text_does_not_hide_a_technique_taken_out() -> None:
    card = AttackCard(techniques=(AttackTechnique(id="T1566", name="Фишинг"),))

    checked, removed = check_attack(card, "Вход через T1190.", KNOWN)

    assert checked.techniques == (AttackTechnique(id="T1190", name=KNOWN["T1190"]),)
    assert removed == ["Техники ATT&CK"]


def test_the_snapshot_knows_the_ics_matrix() -> None:
    assert snapshot()["T0817"] == "Drive-by Compromise"


def test_a_long_decimal_number_is_no_hash() -> None:
    assert extract_indicators("Номер заявки 12345678901234567890123456789012.") == []


def test_an_update_to_a_four_number_version_is_no_address() -> None:
    assert extract_indicators("Обновите до 20.9.10.1, сервер 185.12.4.7.") == ["185.12.4[.]7"]
