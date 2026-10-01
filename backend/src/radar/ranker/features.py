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
    "explore",
    "position",
)
# Readers open what is on top more often, whatever it is. Training sees the
# real place of each article, so the model can tell that pull apart from
# relevance; scoring puts every article on the same place.
SCORING_POSITION = 1.0


def served(parts: Mapping[str, float], score: float, confidence: float) -> dict[str, float]:
    """The features of one article as the served event stores them."""
    return {**parts, "score": score, "confidence": confidence}


def matrix(rows: Sequence[Mapping[str, float]]) -> np.ndarray:
    """One row per article, one column per feature; missing ones are zero."""
    return np.array(
        [[float(row.get(name, 0.0)) for name in FEATURES] for row in rows], dtype=np.float32
    ).reshape(len(rows), len(FEATURES))
