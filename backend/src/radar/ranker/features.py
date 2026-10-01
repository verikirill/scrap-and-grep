"""What the model sees of one served article.

The served event records these numbers as they were at the moment of
serving, and training reads them from there: the model learns from exactly
what serving will give it.
"""

from collections.abc import Mapping, Sequence

import numpy as np

FEATURES = (
    "score",
    "relevance",
    "interest",
    "resume",
    "learned",
    "fresh",
    "source",
    "collab",
    "avoid",
    "read",
    "confidence",
)
# Readers open what is on top more often, whatever it is. The place is not a
# feature: LightGBM learns one bias factor per band of places from it
# (unbiased LambdaMART) and leaves it out of the score.
_FIRST_SCREEN = 10


def served(parts: Mapping[str, float], score: float, confidence: float) -> dict[str, float]:
    """The features of one article as the served event stores them."""
    return {**parts, "score": score, "confidence": confidence}


def matrix(rows: Sequence[Mapping[str, float]], names: Sequence[str] = FEATURES) -> np.ndarray:
    """One row per article, one column per feature; a missing feature is zero."""
    return np.array(
        [[float(row.get(name, 0.0)) for name in names] for row in rows], dtype=np.float32
    ).reshape(len(rows), len(names))


def position_band(position: int) -> int:
    """Every place of the first screen on its own, then wider bands."""
    if position <= _FIRST_SCREEN:
        return max(0, position - 1)
    if position <= 2 * _FIRST_SCREEN:
        return _FIRST_SCREEN
    if position <= 4 * _FIRST_SCREEN:
        return _FIRST_SCREEN + 1
    return _FIRST_SCREEN + 2
