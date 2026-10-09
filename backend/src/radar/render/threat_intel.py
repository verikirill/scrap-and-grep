"""A digest's machine-readable side: its indicators of compromise, the
vulnerabilities it names and the ATT&CK techniques it reports, as a STIX 2.1
bundle, a MISP event and a CSV.

Everything comes from the entries' cards, which were checked against the
articles' text (radar.cards): nothing here is asked of the model, so a SOC can
load the file into its platform on the strength of what the articles printed.
Identifiers are derived from the values, so the same indicator keeps its id
in every export and a platform merges it instead of doubling it.
"""

import csv
import io
import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from radar.indicators import refang
from radar.views import DigestView, ItemView

Kind = Literal["ipv4", "domain", "url", "md5", "sha1", "sha256", "vulnerability", "technique"]

# A namespace of our own: the ids depend on the value alone, not on the run.
_NAMESPACE = uuid.UUID("6f1d4c52-2b8e-5a0e-9c43-5c7a8f0e2d17")
_PRODUCER = "Scrap&Grep"
_IPV4_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")
_HASH_KINDS: dict[int, Kind] = {32: "md5", 40: "sha1", 64: "sha256"}
_VULN_RE = re.compile(r"^(?:CVE-\d{4}-\d{4,}|BDU:\d{4}-\d{5})$", re.IGNORECASE)


@dataclass(frozen=True)
class Observation:
    """One thing a defender can act on, with the entry that reported it."""

    kind: Kind
    # As a machine reads it: "1.2.3.4", "http://evil.example/x", "CVE-2026-1".
    value: str
    # As the article printed it and as it is safe to paste into a chat: defanged.
    shown: str
    # The ATT&CK name of a technique; empty for the rest.
    name: str
    headline: str
    url: str
    published: datetime


def _indicator_kind(value: str) -> Kind | None:
    if _IPV4_RE.match(value):
        return "ipv4"
    if value.startswith(("http://", "https://")):
        return "url"
    if re.fullmatch(r"[a-f0-9]+", value) and len(value) in _HASH_KINDS:
        return _HASH_KINDS[len(value)]
    if "." in value and " " not in value:
        return "domain"
    return None


def _entries(view: DigestView) -> list[ItemView]:
    return [item for topic in view.topics for item in topic.items]


def observations(view: DigestView) -> list[Observation]:
    """What the digest's entries give a defender, each value once, in the
    order of the entries: the first entry that reports a value owns it."""
    found: dict[tuple[Kind, str], Observation] = {}

    def add(item: ItemView, kind: Kind, value: str, shown: str, name: str = "") -> None:
        found.setdefault(
            (kind, value),
            Observation(kind, value, shown, name, item.headline, item.url, item.published_at),
        )

    for item in _entries(view):
        if item.attack is not None:
            for shown in item.attack.indicators:
                value = refang(shown)
                kind = _indicator_kind(value)
                if kind is not None:
                    add(item, kind, value, shown)
            for technique in item.attack.techniques:
                add(item, "technique", technique.id, technique.id, technique.name)
            ids = list(item.attack.vulnerabilities)
        else:
            ids = []
        if item.vulnerability is not None:
            ids += item.vulnerability.ids
        for raw in ids:
            if _VULN_RE.match(raw.strip()):
                vuln = raw.strip().upper()
                add(item, "vulnerability", vuln, vuln)
    return list(found.values())


def _id(object_type: str, key: str) -> str:
    return f"{object_type}--{uuid.uuid5(_NAMESPACE, f'{object_type}:{key}')}"


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


_PATTERNS: dict[str, str] = {
    "ipv4": "ipv4-addr:value",
    "domain": "domain-name:value",
    "url": "url:value",
    "md5": "file:hashes.MD5",
    "sha1": "file:hashes.'SHA-1'",
    "sha256": "file:hashes.'SHA-256'",
}


def _stix_object(item: Observation, created: str, producer: str) -> dict[str, Any]:
    common = {
        "spec_version": "2.1",
        "created": created,
        "modified": created,
        "created_by_ref": producer,
        "external_references": [{"source_name": "article", "url": item.url}],
    }
    if item.kind == "vulnerability":
        references = [{"source_name": "article", "url": item.url}]
        if item.value.startswith("CVE-"):
            references.insert(0, {"source_name": "cve", "external_id": item.value})
        return {
            **common,
            "type": "vulnerability",
            "id": _id("vulnerability", item.value),
            "name": item.value,
            "description": item.headline,
            "external_references": references,
        }
    if item.kind == "technique":
        return {
            **common,
            "type": "attack-pattern",
            "id": _id("attack-pattern", item.value),
            "name": item.name or item.value,
            "external_references": [
                {
                    "source_name": "mitre-attack",
                    "external_id": item.value,
                    "url": "https://attack.mitre.org/techniques/"
                    + item.value.replace(".", "/")
                    + "/",
                },
                {"source_name": "article", "url": item.url},
            ],
        }
    return {
        **common,
        "type": "indicator",
        "id": _id("indicator", f"{item.kind}:{item.value}"),
        "name": item.shown,
        "description": item.headline,
        "indicator_types": ["malicious-activity"],
        "pattern": f"[{_PATTERNS[item.kind]} = '{_quote(item.value)}']",
        "pattern_type": "stix",
        "valid_from": _stamp(item.published),
    }


def render_stix(view: DigestView) -> str:
    """A STIX 2.1 bundle: who made it, a report for the digest, and an
    indicator, vulnerability or attack pattern for each observation."""
    created = _stamp(view.finished_at or view.created_at)
    producer = {
        "type": "identity",
        "spec_version": "2.1",
        "id": _id("identity", _PRODUCER),
        "created": created,
        "modified": created,
        "name": _PRODUCER,
        "identity_class": "system",
    }
    objects = [_stix_object(item, created, producer["id"]) for item in observations(view)]
    report = {
        "type": "report",
        "spec_version": "2.1",
        "id": _id("report", str(view.id)),
        "created": created,
        "modified": created,
        "created_by_ref": producer["id"],
        "name": view.title or view.profile_name,
        "description": f"Выпуск «{view.profile_name}» за "
        f"{view.period_start:%d.%m.%Y} - {view.period_end:%d.%m.%Y}",
        "published": created,
        "report_types": ["threat-report"],
        # A report must reference something: with no observations it names its author.
        "object_refs": [obj["id"] for obj in objects] or [producer["id"]],
    }
    bundle = {
        "type": "bundle",
        "id": _id("bundle", str(view.id)),
        "objects": [producer, report, *objects],
    }
    return json.dumps(bundle, ensure_ascii=False, indent=2)


# MISP's attribute types and categories for each kind.
_MISP: dict[str, tuple[str, str, bool]] = {
    "ipv4": ("ip-dst", "Network activity", True),
    "domain": ("domain", "Network activity", True),
    "url": ("url", "Network activity", True),
    "md5": ("md5", "Payload delivery", True),
    "sha1": ("sha1", "Payload delivery", True),
    "sha256": ("sha256", "Payload delivery", True),
    "vulnerability": ("vulnerability", "External analysis", False),
}


def render_misp(view: DigestView) -> str:
    """A MISP event in the JSON its import takes: indicators as attributes
    flagged for detection, vulnerabilities as attributes for context and
    techniques as tags of MISP's ATT&CK galaxy."""
    items = observations(view)
    attributes = [
        {
            "uuid": str(uuid.uuid5(_NAMESPACE, f"misp:{item.kind}:{item.value}")),
            "type": _MISP[item.kind][0],
            "category": _MISP[item.kind][1],
            "to_ids": _MISP[item.kind][2],
            "value": item.value,
            "comment": f"{item.headline} ({item.url})",
            "timestamp": str(int(item.published.timestamp())),
        }
        for item in items
        if item.kind in _MISP
    ]
    tags = [{"name": "tlp:clear"}] + [
        {"name": f'misp-galaxy:mitre-attack-pattern="{item.name or item.value} - {item.value}"'}
        for item in items
        if item.kind == "technique"
    ]
    finished = view.finished_at or view.created_at
    event = {
        "Event": {
            "uuid": str(uuid.uuid5(_NAMESPACE, f"misp-event:{view.id}")),
            "info": f"{_PRODUCER}: {view.title or view.profile_name}",
            "date": f"{view.period_end:%Y-%m-%d}",
            "timestamp": str(int(finished.timestamp())),
            # Medium threat, analysis complete, this organisation only.
            "threat_level_id": "2",
            "analysis": "2",
            "distribution": "0",
            "Orgc": {"name": _PRODUCER},
            "Attribute": attributes,
            "Tag": tags,
        }
    }
    return json.dumps(event, ensure_ascii=False, indent=2)


def render_csv(view: DigestView) -> str:
    """One row per observation, for a spreadsheet or a firewall's import."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["type", "value", "defanged", "name", "headline", "url", "published"])
    for item in observations(view):
        writer.writerow(
            [
                item.kind,
                item.value,
                item.shown,
                item.name,
                item.headline,
                item.url,
                item.published.astimezone(UTC).isoformat(),
            ]
        )
    return out.getvalue()
