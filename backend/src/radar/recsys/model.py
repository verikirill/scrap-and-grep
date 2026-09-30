"""Types shared between the recommender and the digest pipeline."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Personal:
    """How a reader's behaviour changes the score of one digest candidate."""

    delta: float = 0.0
    rejected: bool = False
    note: str = ""
