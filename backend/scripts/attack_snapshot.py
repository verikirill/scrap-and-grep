"""Rebuild the ATT&CK snapshot shipped with the package: the id and the name
of every enterprise technique, for a stack that cannot reach MITRE.

    uv run python scripts/attack_snapshot.py

Takes the bundle from attack-stix-data (about 45 MB) and writes
src/radar/vulns/attack_snapshot.json, sorted, so a diff shows what changed.
"""

import json
from pathlib import Path

import httpx

from radar.config import get_settings
from radar.vulns.attack import parse_stix

OUT = Path(__file__).resolve().parents[1] / "src" / "radar" / "vulns" / "attack_snapshot.json"


def main() -> None:
    response = httpx.get(get_settings().attack_url, timeout=120, follow_redirects=True)
    response.raise_for_status()
    techniques = dict(sorted(parse_stix(response.json()).items()))
    OUT.write_text(
        json.dumps(techniques, ensure_ascii=False, indent=0, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"{len(techniques)} techniques -> {OUT}")


main()
