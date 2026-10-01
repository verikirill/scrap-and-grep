"""How a profile's interest follows its reader: the pure part, no database."""

import numpy as np

from radar.recsys.adapt import (
    FACTOR_MAX,
    FACTOR_MIN,
    adapt_interest,
    common_words,
    groups_of,
    title_key,
)
from radar.recsys.taste import Signal


def _unit(*values: float) -> np.ndarray:
    vector = np.zeros(8, dtype=np.float32)
    vector[: len(values)] = values
    return vector / np.linalg.norm(vector)


def _mark(article_id: int, kind: str, vector: np.ndarray, age_days: float = 1.0) -> Signal:
    return Signal(article_id, kind, age_days, source_id=1, title=f"t{article_id}", vector=vector)


BASE = _unit(1.0, 0.0)
NEAR_LIKED = _unit(0.6, 0.8)
FAR_DISLIKED = _unit(0.0, 0.0, 1.0)


def test_an_interest_with_no_marks_stays_as_stated() -> None:
    state = adapt_interest("ics", BASE, [], skipped=[])

    assert state.factor == 1.0
    assert state.vector is None
    assert state.drift == 0.0


def test_likes_raise_the_weight_and_turn_the_interest_towards_what_was_liked() -> None:
    likes = [_mark(index, "like", NEAR_LIKED) for index in range(5)]

    state = adapt_interest("ics", BASE, likes, skipped=[])

    assert 1.0 < state.factor <= FACTOR_MAX
    assert state.vector is not None
    # Closer to the liked articles than the stated interest was, but still
    # recognisably the same interest.
    assert float(state.vector @ NEAR_LIKED) > float(BASE @ NEAR_LIKED)
    assert float(state.vector @ BASE) > 0.8
    assert 0.0 < state.drift < 0.2


def test_rejections_and_scrolling_past_lower_the_weight_within_bounds() -> None:
    marks = [_mark(index, "dislike", FAR_DISLIKED) for index in range(40)]

    state = adapt_interest("ics", BASE, marks, skipped=[1.0] * 200)

    assert FACTOR_MIN <= state.factor < 1.0
    assert state.factor == FACTOR_MIN or state.factor > FACTOR_MIN
    # Dislikes alone do not move the meaning: there is nothing to move towards.
    assert state.vector is None


def test_one_like_is_not_enough_to_move_the_meaning() -> None:
    state = adapt_interest("ics", BASE, [_mark(1, "like", NEAR_LIKED)], skipped=[])

    assert state.vector is None
    assert state.factor > 1.0


def test_old_marks_count_for_less_than_fresh_ones() -> None:
    fresh = adapt_interest("a", BASE, [_mark(i, "like", NEAR_LIKED, 1) for i in range(4)], [])
    stale = adapt_interest("a", BASE, [_mark(i, "like", NEAR_LIKED, 90) for i in range(4)], [])

    assert fresh.factor > stale.factor >= 1.0


def test_an_opened_then_disliked_article_counts_as_a_rejection() -> None:
    marks = [_mark(1, "open", NEAR_LIKED), _mark(1, "dislike", NEAR_LIKED)]

    state = adapt_interest("a", BASE, marks, skipped=[])

    assert state.positives == 0.0
    assert state.negatives > 0.0


def test_liked_articles_on_two_subjects_form_two_groups() -> None:
    first = [_mark(i, "like", _unit(1.0, 0.05 * i)) for i in range(4)]
    second = [_mark(10 + i, "like", _unit(0.0, 0.0, 0.0, 1.0, 0.05 * i)) for i in range(4)]
    stray = [_mark(99, "like", _unit(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0))]

    groups = groups_of([(1.0, mark) for mark in [*first, *second, *stray]], min_size=3)

    assert sorted(sorted(mark.article_id for mark in group) for group in groups) == [
        [0, 1, 2, 3],
        [10, 11, 12, 13],
    ]


def test_common_words_name_what_titles_share_and_skip_known_ones() -> None:
    titles = [
        "Ransomware атакует подстанции в Европе",
        "Новая волна ransomware против подстанций",
        "Ransomware: как защищают подстанции",
    ]

    assert common_words(titles, known={"европе"})[:2] == ["ransomware", "подстанции"]
    assert "ransomware" not in common_words(titles, known={"ransomware"})


def test_names_that_differ_in_endings_are_one_suggestion() -> None:
    assert title_key("Уязвимости в цепочке поставок") == title_key("Уязвимости в цепочках поставок")
    assert title_key("Безопасность контейнеров") != title_key("Уязвимости ИИ-агентов")
