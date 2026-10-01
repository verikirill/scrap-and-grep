"""When the learned feed ranker is switched on, kept, retired, and what it changes."""

from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np

from radar.ranker.serving import learned_order
from radar.ranker.train import (
    LABEL_LIKED,
    LABEL_OPENED,
    LABEL_SEEN,
    MARGIN,
    Lists,
    assemble,
    evaluate,
)
from radar.recsys.ranking import Ranked

END = datetime(2026, 9, 30, tzinfo=UTC)


def lists_where_freshness_decides(count: int, *, seed: int = 1) -> Lists:
    """Served lists over two weeks. Readers act on fresh articles; the hand
    score is noise, so it knows nothing a model could not learn."""
    rng = np.random.default_rng(seed)
    rows: list[tuple[Any, int, dict[str, float], datetime, int]] = []
    for index in range(count):
        served_at = END - timedelta(days=14) + timedelta(days=14) * index / count
        for position in range(1, 21):
            fresh = rng.random()
            label = LABEL_LIKED if fresh > 0.8 else LABEL_OPENED if fresh > 0.6 else LABEL_SEEN
            features = {"score": rng.random(), "fresh": fresh, "confidence": 0.5}
            rows.append((index, position, features, served_at, label))
    return assemble(rows)


class Fixed:
    """A model stand-in that scores by a function of the features."""

    version = "stub"

    def __init__(self, score: Any) -> None:
        self.score = score

    def scores(self, rows: list[dict[str, float]]) -> np.ndarray:
        return np.array([self.score(row) for row in rows])


def test_a_model_that_finds_what_the_hand_blend_misses_is_switched_on() -> None:
    outcome = evaluate(lists_where_freshness_decides(600), END)

    assert outcome.status == "active"
    assert outcome.metrics["model_ndcg"] >= outcome.metrics["hand_ndcg"] + MARGIN
    assert outcome.booster is not None


def test_too_little_data_keeps_the_hand_blend() -> None:
    outcome = evaluate(lists_where_freshness_decides(40), END)

    assert outcome.status == "rejected"
    assert outcome.booster is None
    assert outcome.note.startswith("Мало данных")


def test_a_model_already_on_is_retired_once_it_loses_to_the_hand_blend() -> None:
    lists = lists_where_freshness_decides(40)
    # Puts the stalest first: worse than the hand blend's noise.
    stale_first = Fixed(lambda row: -row["fresh"])
    fresh_first = Fixed(lambda row: row["fresh"])

    assert evaluate(lists, END, stale_first).keep_active is False  # type: ignore[arg-type]
    assert evaluate(lists, END, fresh_first).keep_active is True  # type: ignore[arg-type]


def test_the_model_changes_the_order_but_not_the_scale_of_scores() -> None:
    pool = [
        Ranked(article_id, score, {"fresh": fresh}, {})
        for article_id, score, fresh in (
            (1, 0.9, 0.1),
            (2, 0.7, 0.5),
            (3, 0.5, 0.9),
        )
    ]

    order = learned_order(Fixed(lambda row: row["fresh"]), pool, 0.5)  # type: ignore[arg-type]
    broken = learned_order(Fixed(lambda row: row["missing"]), pool, 0.5)  # type: ignore[arg-type]

    # The freshest gets the best score of the pool, the stalest the worst.
    assert order == {3: 0.9, 2: 0.7, 1: 0.5}
    # A model that fails leaves the hand order alone.
    assert broken == {}
