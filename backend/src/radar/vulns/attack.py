"""MITRE ATT&CK techniques by id, Enterprise and ICS, with the names a card shows.

A local copy of mitre/cti (enterprise-attack and ics-attack, without revoked
and deprecated techniques), taken on 3 October 2026: the stack never asks the
internet for it. A card names a technique only where the article gives its
id; the model is not asked to map what attackers did onto ATT&CK.
"""

import json
import re
from functools import cache
from importlib.resources import files

TECHNIQUE_RE = re.compile(r"\bT[01]\d{3}(?:\.\d{3})?\b")
MAX_TECHNIQUES = 12


@cache
def technique_names() -> dict[str, str]:
    raw = files("radar.vulns").joinpath("attack_techniques.json").read_text("utf-8")
    names: dict[str, str] = json.loads(raw)
    return names


def techniques(text: str) -> tuple[str, ...]:
    """The techniques a text names by id, in its order, as "T1190 Exploit
    Public-Facing Application". An id the copy does not know is left out: a
    product called "T1000" is not a technique."""
    names = technique_names()
    found = dict.fromkeys(tid for tid in TECHNIQUE_RE.findall(text) if tid in names)
    return tuple(f"{tid} {names[tid]}" for tid in found)[:MAX_TECHNIQUES]
