"""Reader signals and how much each one says."""

from typing import Literal

Kind = Literal["like", "dislike", "save", "hide", "open"]

KIND_LIKE: Kind = "like"
KIND_DISLIKE: Kind = "dislike"
KIND_SAVE: Kind = "save"
KIND_HIDE: Kind = "hide"
KIND_OPEN: Kind = "open"

# Saving is a stronger commitment than a like; opening the source is weak
# evidence on its own (a headline can disappoint). A dislike says "not this
# topic", hiding may only mean "not now".
SIGNAL_WEIGHT: dict[str, float] = {
    KIND_SAVE: 1.2,
    KIND_LIKE: 1.0,
    KIND_OPEN: 0.4,
    KIND_HIDE: -0.7,
    KIND_DISLIKE: -1.0,
}
# A like and a dislike cannot both hold; setting one clears the other.
OPPOSITE: dict[str, str] = {KIND_LIKE: KIND_DISLIKE, KIND_DISLIKE: KIND_LIKE}
# Articles with these signals leave the feed and the reader's digests.
REJECTING: frozenset[str] = frozenset({KIND_DISLIKE, KIND_HIDE})

# Interests drift: a signal loses half of its weight in three weeks.
HALF_LIFE_DAYS = 21.0


def decayed_weight(kind: str, age_days: float) -> float:
    """Signed strength of a signal that is `age_days` old."""
    return SIGNAL_WEIGHT.get(kind, 0.0) * float(0.5 ** (max(0.0, age_days) / HALF_LIFE_DAYS))
