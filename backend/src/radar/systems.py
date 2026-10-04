"""The reader's own systems: which of them an entry is about.

A reader lists the products the company runs ("Cisco ASA", "Siemens S7-1500",
"1С"); an entry that names one is marked and goes first in its topic. The
match is a comparison of words, not the model's judgement, so the list does
not change how an entry is graded and the profile's fingerprint leaves it out.
"""

import re
from collections.abc import Sequence

from radar.domain import ItemSummary

_NOT_WORD = re.compile(r"[\W_]+")
# Russian texts write 1С with a Cyrillic letter, a keyboard often types a
# Latin one: both are the same word.
_SAME_WORD = {"1c": "1с"}


def words(text: str) -> list[str]:
    """Lower case, ё as е, punctuation as a space: "S7-1500" is ["s7", "1500"]."""
    plain = _NOT_WORD.sub(" ", text.lower().replace("ё", "е"))
    return [_SAME_WORD.get(word, word) for word in plain.split()]


def affected_systems(systems: Sequence[str], text: str) -> tuple[str, ...]:
    """The systems the text names, in the profile's order: every word of two
    characters or more of a system is a whole word of the text."""
    present = set(words(text))
    found = []
    for system in systems:
        needed = [word for word in words(system) if len(word) >= 2]
        if needed and all(word in present for word in needed):
            found.append(system)
    return tuple(found)


def entry_text(headline: str, title: str, summary: str, card: ItemSummary) -> str:
    """What an entry says about products: its headline, the original title,
    the summary and the card's fields that name products."""
    parts = [headline, title, summary]
    if card.vulnerability is not None:
        vulnerability = card.vulnerability
        parts += [vulnerability.name, vulnerability.affected, vulnerability.equipment]
    if card.attack is not None:
        attack = card.attack
        parts += [*attack.tools, attack.sectors, attack.affected]
    return "\n".join(parts)
