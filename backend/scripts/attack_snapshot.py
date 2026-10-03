"""Rebuild the ATT&CK snapshot shipped with the package: the id and the name
of every enterprise and ICS technique, for a stack that cannot reach MITRE.

    uv run python scripts/attack_snapshot.py

Takes the bundles from attack-stix-data (about 45 MB and 3 MB) and writes
src/radar/vulns/attack_snapshot.json, sorted, so a diff shows what changed.
"""

import json
from pathlib import Path

import httpx

from radar.config import get_settings
from radar.vulns.attack import parse_stix

OUT = Path(__file__).resolve().parents[1] / "src" / "radar" / "vulns" / "attack_snapshot.json"
# The loader keeps the enterprise matrix fresh; ICS lives in the snapshot only.
ICS_URL = (
    "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/"
    "ics-attack/ics-attack.json"
)


def main() -> None:
    techniques: dict[str, str] = {}
    for url in (get_settings().attack_url, ICS_URL):
        response = httpx.get(url, timeout=120, follow_redirects=True)
        response.raise_for_status()
        techniques |= parse_stix(response.json())
    techniques = dict(sorted(techniques.items()))
    OUT.write_text(
        json.dumps(techniques, ensure_ascii=False, indent=0, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"{len(techniques)} techniques -> {OUT}")


main()
