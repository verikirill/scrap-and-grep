"""The recommender's rules, on hand-made vectors: no database, no model."""

import numpy as np
import pytest

from radar.recsys.ranking import (
    EXPLORE_EVERY,
    Evidence,
    Ranked,
    Weights,
    rerank_for_variety,
    score_article,
    with_exploration,
)
from radar.recsys.signals import HALF_LIFE_DAYS, decayed_weight
from radar.recsys.taste import Facet, Signal, build_taste

WEIGHTS = Weights()


def unit(*values: float) -> np.ndarray:
    vector = np.asarray(values, dtype=np.float32)
    return vector / np.linalg.norm(vector)


def signal(
    article_id: int, kind: str, vector: np.ndarray, *, age: float = 0.0, source: int = 1
) -> Signal:
    return Signal(
        article_id=article_id,
        kind=kind,
        age_days=age,
        source_id=source,
        title=f"Статья {article_id}",
        vector=vector,
    )


def evidence(article_id: int, **z: float) -> Evidence:
    """Evidence with the given z-scores; "learned" and "avoid" name facet kinds."""
    return Evidence(article_id=article_id, source_id=1, age_hours=48.0, z=z)


INTEREST = Facet(key="interest:ics", kind="interest", label="АСУ ТП", vector=unit(1, 0, 0))
RESUME = Facet(key="resume", kind="resume", label="Инженер", vector=unit(0, 1, 0))


def test_a_signal_loses_half_of_its_weight_per_half_life() -> None:
    assert decayed_weight("like", HALF_LIFE_DAYS) == pytest.approx(0.5)
    assert decayed_weight("dislike", 2 * HALF_LIFE_DAYS) == pytest.approx(-0.25)


def test_likes_become_a_learned_facet_and_dislikes_an_avoid_facet() -> None:
    liked, disliked = unit(0, 0, 1), unit(0, 1, 1)
    taste = build_taste(
        [INTEREST],
        [signal(1, "like", liked), signal(2, "save", liked), signal(3, "dislike", disliked)],
    )

    learned, avoid = taste.of_kind("learned"), taste.of_kind("avoid")
    assert len(learned) == 1
    assert len(avoid) == 1
    assert float(learned[0].vector @ liked) == pytest.approx(1.0)
    assert taste.rejected(3)
    assert not taste.rejected(1)


def test_an_article_opened_and_then_disliked_counts_as_rejected() -> None:
    vector = unit(0, 0, 1)

    taste = build_taste([INTEREST], [signal(7, "open", vector), signal(7, "dislike", vector)])

    assert taste.positives == 0
    assert taste.negatives == 1
    assert not taste.of_kind("learned")


def test_two_distinct_themes_give_two_learned_facets() -> None:
    first, second = unit(1, 0, 0, 0), unit(0, 0, 0, 1)
    likes = [signal(index, "like", first) for index in range(4)]
    likes += [signal(index, "like", second) for index in range(4, 8)]

    learned = build_taste([], likes).of_kind("learned")

    assert len(learned) == 2
    closeness = sorted(float(abs(facet.vector @ first)) for facet in learned)
    assert closeness == pytest.approx([0.0, 1.0], abs=1e-5)


def test_confidence_grows_with_the_amount_of_behaviour() -> None:
    vector = unit(1, 1, 0)

    few = build_taste([INTEREST], [signal(1, "like", vector)])
    many = build_taste([INTEREST], [signal(index, "like", vector) for index in range(12)])

    assert 0 < few.confidence < many.confidence == 1.0


def test_an_article_close_to_a_liked_theme_outranks_a_neutral_one() -> None:
    liked = unit(0, 0, 1)
    taste = build_taste([INTEREST], [signal(index, "like", liked) for index in range(6)])
    learned_key = taste.of_kind("learned")[0].key
    neutral = evidence(10, **{"interest:ics": 1.0})
    similar = evidence(11, **{"interest:ics": 1.0, learned_key: 3.0})

    scores = {
        item.article_id: score_article(item, taste, WEIGHTS, semantic=True).score
        for item in (neutral, similar)
    }

    assert scores[11] > scores[10]


def test_an_article_close_to_a_rejected_theme_is_pushed_down() -> None:
    rejected = unit(0, 0, 1)
    taste = build_taste([INTEREST], [signal(index, "dislike", rejected) for index in range(3)])
    avoid_key = taste.of_kind("avoid")[0].key
    clean = evidence(10, **{"interest:ics": 3.0})
    tainted = evidence(11, **{"interest:ics": 3.0, avoid_key: 4.0})

    clean_score = score_article(clean, taste, WEIGHTS, semantic=True)
    tainted_score = score_article(tainted, taste, WEIGHTS, semantic=True)

    assert tainted_score.score < clean_score.score
    assert tainted_score.parts["avoid"] < 0
    # Merely average closeness to the rejected theme costs nothing.
    assert (
        score_article(evidence(12, **{avoid_key: 0.5}), taste, WEIGHTS, semantic=True).parts[
            "avoid"
        ]
        == 0
    )


def test_a_resume_match_alone_cannot_outrank_an_equal_interest_match() -> None:
    taste = build_taste([INTEREST, RESUME], [])
    by_interest = evidence(1, **{"interest:ics": 3.0, "resume": 0.0})
    by_resume = evidence(2, **{"interest:ics": 0.0, "resume": 3.0})

    assert (
        score_article(by_interest, taste, WEIGHTS, semantic=True).score
        > score_article(by_resume, taste, WEIGHTS, semantic=True).score
    )


def test_a_reader_known_only_by_resume_still_gets_a_ranking() -> None:
    taste = build_taste([RESUME], [])

    close = score_article(evidence(1, resume=3.0), taste, WEIGHTS, semantic=True)
    far = score_article(evidence(2, resume=-1.0), taste, WEIGHTS, semantic=True)

    assert close.score > WEIGHTS.min_score > far.score
    assert close.best == {"resume": "resume"}


def test_a_read_article_sinks() -> None:
    taste = build_taste([INTEREST], [])
    item = evidence(1, **{"interest:ics": 3.0})

    fresh = score_article(item, taste, WEIGHTS, semantic=True)
    read = score_article(item, taste, WEIGHTS, semantic=True, read=True)

    assert read.score == pytest.approx(fresh.score - WEIGHTS.read_penalty)


def ranked(article_id: int, score: float) -> Ranked:
    return Ranked(article_id, score, {"fresh": 0.0, "avoid": 0.0}, {})


def test_variety_rerank_drops_a_copy_and_lets_a_different_story_in() -> None:
    story, other = unit(1, 0, 0), unit(0, 1, 0)
    vectors = {1: story, 2: unit(1, 0.05, 0), 3: other}
    items = [ranked(1, 0.9), ranked(2, 0.88), ranked(3, 0.6)]

    feed = rerank_for_variety(
        items, vectors, {1: 1, 2: 2, 3: 3}, duplicate_threshold=0.9, variety=0.75, limit=10
    )

    assert [item.article_id for item in feed] == [1, 3]


def test_variety_rerank_prefers_a_new_angle_over_a_slightly_better_repeat() -> None:
    topic = unit(1, 0, 0)
    # Article 2 is on the same topic as the leader (cosine 0.8, not a copy);
    # article 3 is about something else and scores a little lower.
    vectors = {1: topic, 2: unit(0.8, 0.6, 0), 3: unit(0, 0, 1)}
    items = [ranked(1, 0.9), ranked(2, 0.8), ranked(3, 0.75)]

    feed = rerank_for_variety(
        items, vectors, {1: 1, 2: 1, 3: 2}, duplicate_threshold=0.95, variety=0.75, limit=10
    )

    assert [item.article_id for item in feed] == [1, 3, 2]


def test_exploration_takes_every_seventh_place_and_is_stable_within_a_day() -> None:
    feed = [ranked(article_id, 0.9) for article_id in range(1, 21)]
    spare = [ranked(article_id, 0.1) for article_id in range(100, 110)]

    first = with_exploration(feed, spare, seed="reader:2026-09-30", limit=30)
    again = with_exploration(feed, spare, seed="reader:2026-09-30", limit=30)
    tomorrow = with_exploration(feed, spare, seed="reader:2026-10-01", limit=30)

    places = [index + 1 for index, item in enumerate(first) if item.explore]
    assert places == [EXPLORE_EVERY, 2 * EXPLORE_EVERY, 3 * EXPLORE_EVERY]
    assert [item.article_id for item in first] == [item.article_id for item in again]
    picks = [item.article_id for item in first if item.explore]
    assert picks != [item.article_id for item in tomorrow if item.explore]


def test_exploration_never_offers_what_is_close_to_a_rejected_theme() -> None:
    feed = [ranked(article_id, 0.9) for article_id in range(1, 15)]
    tainted = Ranked(100, 0.1, {"fresh": 0.05, "avoid": -0.2}, {})
    clean = Ranked(101, 0.1, {"fresh": 0.0, "avoid": 0.0}, {})

    result = with_exploration(feed, [tainted, clean], seed="s", limit=20)

    assert [item.article_id for item in result if item.explore] == [101]
