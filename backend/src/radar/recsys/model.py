"""Types shared between the recommender and the digest pipeline."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Learned:
    """What one interest of an adaptive profile has learned from its reader."""

    factor: float = 1.0
    # The interest's search vector turned towards what was liked; None while
    # the interest searches by its stated text.
    vector: list[float] | None = None
    drift: float = 0.0
    positives: float = 0.0
    negatives: float = 0.0
    skipped: int = 0


WEIGHT_MIN = 0.5
WEIGHT_MAX = 1.5


def adapted_weight(weight: float, learned: Learned | None) -> float:
    """The stated weight times what was learned, within the weights a profile allows."""
    if learned is None:
        return weight
    return float(min(WEIGHT_MAX, max(WEIGHT_MIN, weight * learned.factor)))


@dataclass(frozen=True, slots=True)
class Personal:
    """How a reader's behaviour changes the score of one digest candidate."""

    delta: float = 0.0
    rejected: bool = False
    note: str = ""
