# ruff: noqa: F811  (the digest fixture is imported from test_render)
"""The digest as threat intelligence: what a SOC loads into its platform must
be the articles' own indicators, typed right and with ids that stay put."""

import csv
import io
import json

from radar.domain import AttackCard, AttackTechnique, VulnerabilityCard
from radar.render.threat_intel import observations, render_csv, render_misp, render_stix
from radar.views import DigestView, TopicView
from tests.test_render import _item, digest  # noqa: F401  (fixtures)

SHA256 = "a" * 64


def _with_cards(view: DigestView) -> DigestView:
    attack = _item(
        10,
        "Атака на подстанцию",
        kind="attack",
        attack=AttackCard(
            indicators=("185.12.44[.]7", "hxxps://evil[.]example/drop", SHA256, "evil[.]example"),
            techniques=(AttackTechnique(id="T1190", name="Exploit Public-Facing Application"),),
            vulnerabilities=("CVE-2026-1001",),
        ),
    )
    vuln = _item(
        11,
        "Уязвимость в ПЛК",
        kind="vulnerability",
        # The same CVE again and a BDU id: each value once, owned by the first entry.
        vulnerability=VulnerabilityCard(ids=("cve-2026-1001", "BDU:2026-01234")),
    )
    return view.model_copy(
        update={"topics": [TopicView(title="Атаки", overview="", items=[attack, vuln])]}
    )


def test_indicators_are_refanged_typed_and_listed_once(digest: DigestView) -> None:
    found = {(item.kind, item.value) for item in observations(_with_cards(digest))}

    assert found == {
        ("ipv4", "185.12.44.7"),
        ("url", "https://evil.example/drop"),
        ("sha256", SHA256),
        ("domain", "evil.example"),
        ("technique", "T1190"),
        ("vulnerability", "CVE-2026-1001"),
        ("vulnerability", "BDU:2026-01234"),
    }


def test_the_stix_bundle_has_valid_patterns_and_stable_ids(digest: DigestView) -> None:
    view = _with_cards(digest)
    bundle = json.loads(render_stix(view))
    again = json.loads(render_stix(view))

    by_type: dict[str, list[dict[str, object]]] = {}
    for obj in bundle["objects"]:
        by_type.setdefault(obj["type"], []).append(obj)
    patterns = {obj["pattern"] for obj in by_type["indicator"]}
    assert "[ipv4-addr:value = '185.12.44.7']" in patterns
    assert f"[file:hashes.'SHA-256' = '{SHA256}']" in patterns
    assert by_type["attack-pattern"][0]["external_references"][0]["external_id"] == "T1190"
    (report,) = by_type["report"]
    assert set(report["object_refs"]) == {
        obj["id"] for obj in bundle["objects"] if obj["type"] not in {"identity", "report"}
    }
    # A second export of the same digest gives the same ids: a platform merges, not doubles.
    assert [obj["id"] for obj in bundle["objects"]] == [obj["id"] for obj in again["objects"]]


def test_a_digest_without_indicators_still_gives_a_valid_report(digest: DigestView) -> None:
    bundle = json.loads(render_stix(digest))

    (report,) = [obj for obj in bundle["objects"] if obj["type"] == "report"]
    assert report["object_refs"]


def test_misp_flags_indicators_for_detection_and_not_vulnerabilities(digest: DigestView) -> None:
    event = json.loads(render_misp(_with_cards(digest)))["Event"]

    by_value = {attribute["value"]: attribute for attribute in event["Attribute"]}
    assert by_value["185.12.44.7"]["type"] == "ip-dst"
    assert by_value["185.12.44.7"]["to_ids"] is True
    assert by_value["CVE-2026-1001"]["to_ids"] is False
    assert {"name": "tlp:clear"} in event["Tag"]
    assert any(tag["name"].endswith('- T1190"') for tag in event["Tag"])


def test_the_csv_keeps_the_defanged_form_next_to_the_value(digest: DigestView) -> None:
    rows = list(csv.DictReader(io.StringIO(render_csv(_with_cards(digest)))))

    ip = next(row for row in rows if row["type"] == "ipv4")
    assert (ip["value"], ip["defanged"]) == ("185.12.44.7", "185.12.44[.]7")
    assert ip["headline"] == "Атака на подстанцию"
