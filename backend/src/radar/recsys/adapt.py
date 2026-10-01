"""How a profile's interests follow their reader. Pure: no database, no model calls.

Two things move, both bounded and both recomputed from all marks at once:

- the weight of an interest, by how often what it brings is liked. A Beta
  posterior of the like rate, so a few marks move it a little and many marks
  move it more, and the factor stays within FACTOR_MIN..FACTOR_MAX;
- the meaning of an interest: its search vector turns towards the articles
  the reader liked under it and away from the ones they rejected (Rocchio's
  relevance feedback), never so far that it stops being the same interest.

Liked articles no interest covers become suggested new interests, rejected
ones suggested exclusions; groups_of and common_words prepare those.
"""

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np
from sklearn.cluster import AgglomerativeClustering

from radar.recsys.signals import HALF_LIFE_DAYS
from radar.recsys.taste import Signal, net_weights
from radar.text import STOPWORDS, tokenize

# Chosen on the evaluation week (scripts/eval_adaptation.py, docs/eval):
# the like rate of one screen predicts little, and a weight that moves by a
# quarter cost more than it gave; a tenth does not.
FACTOR_MIN = 0.9
FACTOR_MAX = 1.1
# Beta(2, 2): with no marks the like rate is taken as one in two.
_PRIOR = 2.0
# Scrolling past an article as a weak "no": 0.1 per article made the next
# days rank worse (+0.013 nDCG@20 against +0.022 without), so it is off.
# Impressions are still recorded and shown to the reader.
SKIP_WEIGHT = 0.0
# A seen article counts at most this many times, however often it was shown.
_SKIP_TIMES_CAP = 3
# Positive weight needed before the meaning of an interest moves at all, and
# the weight at which it moves as far as it ever does.
MIN_POSITIVE_TO_MOVE = 2.0
_FULL_TRUST = 6.0
# Rocchio coefficients at full trust: the stated interest keeps weight 1.
_TOWARDS_LIKED = 0.5
_AWAY_FROM_REJECTED = 0.25


@dataclass(frozen=True, slots=True)
class InterestState:
    interest_id: str
    # Multiplies the stated weight of the interest.
    factor: float = 1.0
    # The moved search vector, None while the interest keeps its stated one.
    vector: np.ndarray | None = None
    # 1 - cosine between the stated and the moved vector.
    drift: float = 0.0
    positives: float = 0.0
    negatives: float = 0.0
    skipped: int = 0


def _unit(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm else vector


def _decay(age_days: float) -> float:
    return float(0.5 ** (max(0.0, age_days) / HALF_LIFE_DAYS))


def _centroid(weighted: Sequence[tuple[float, Signal]]) -> np.ndarray | None:
    usable = [weight * signal.vector for weight, signal in weighted if signal.vector is not None]
    return _unit(np.sum(np.stack(usable), axis=0)) if usable else None


def adapt_interest(
    interest_id: str,
    base: np.ndarray | None,
    marks: Sequence[Signal],
    skipped: Sequence[float],
) -> InterestState:
    """The state of one interest after the reader's marks on what it brought.

    `marks` are the reader's signals on articles this interest covers;
    `skipped` holds the age in days of every article it covers that the
    reader saw and left without a mark.
    """
    net = net_weights(marks)
    liked = [(weight, signal) for weight, signal in net.values() if weight > 0]
    rejected = [(-weight, signal) for weight, signal in net.values() if weight < 0]
    positives = sum(weight for weight, _ in liked)
    explicit_negatives = sum(weight for weight, _ in rejected)
    negatives = explicit_negatives + SKIP_WEIGHT * sum(_decay(age) for age in skipped)

    rate = (_PRIOR + positives) / (2 * _PRIOR + positives + negatives)
    factor = float(np.clip(1.0 + (FACTOR_MAX - 1.0) * 2 * (rate - 0.5), FACTOR_MIN, FACTOR_MAX))

    vector: np.ndarray | None = None
    drift = 0.0
    towards = _centroid(liked)
    if base is not None and towards is not None and positives >= MIN_POSITIVE_TO_MOVE:
        stated = _unit(base.astype(np.float32))
        moved = stated + _TOWARDS_LIKED * min(1.0, positives / _FULL_TRUST) * towards
        away = _centroid(rejected)
        if away is not None:
            moved -= _AWAY_FROM_REJECTED * min(1.0, explicit_negatives / _FULL_TRUST) * away
        vector = _unit(moved)
        drift = max(0.0, 1.0 - float(stated @ vector))

    return InterestState(
        interest_id=interest_id,
        factor=round(factor, 4),
        vector=vector,
        drift=round(drift, 4),
        positives=round(positives, 3),
        negatives=round(negatives, 3),
        skipped=len(skipped),
    )


def skip_ages(times_and_ages: Iterable[tuple[int, float]]) -> list[float]:
    """Expand (times seen, age) pairs into one age per counted showing."""
    return [age for times, age in times_and_ages for _ in range(min(times, _SKIP_TIMES_CAP))]


def groups_of(
    weighted: Sequence[tuple[float, Signal]], *, min_size: int, max_groups: int = 4
) -> list[list[Signal]]:
    """Articles on one subject, largest groups first; strays are dropped."""
    usable = [(weight, signal) for weight, signal in weighted if signal.vector is not None]
    if len(usable) < min_size:
        return []
    vectors = np.stack([signal.vector for _, signal in usable if signal.vector is not None])
    # As many clusters as groups of the minimum size could fill: an article on
    # a subject of its own stays alone and is dropped, instead of being pulled
    # into the nearest group and blurring it.
    count = max(1, len(usable) // min_size)
    labels = (
        np.zeros(len(usable), dtype=int)
        if count == 1
        else AgglomerativeClustering(n_clusters=count, linkage="ward").fit_predict(vectors)
    )
    groups: dict[int, list[tuple[float, Signal]]] = {}
    for item, label in zip(usable, labels.tolist(), strict=True):
        groups.setdefault(label, []).append(item)
    ordered = sorted(groups.values(), key=lambda group: -sum(weight for weight, _ in group))
    return [
        [signal for _, signal in sorted(group, key=lambda item: -item[0])]
        for group in ordered
        if len(group) >= min_size
    ][:max_groups]


_TITLE_STEM = 5


def title_key(title: str) -> str:
    """Titles that differ only in word endings and order give the same key.

    Five letters cover a Russian word with any ending ("цепочке", "цепочках");
    in a title of a few words two different subjects rarely share them all.
    """
    return " ".join(
        sorted({token[:_TITLE_STEM] for token in tokenize(title) if token not in STOPWORDS})
    )


def _stem(token: str) -> str:
    # The same rule the MCP search uses: Russian endings differ in the last
    # two letters ("подстанции", "подстанций").
    return token[: max(4, len(token) - 2)]


def common_words(titles: Sequence[str], *, known: Iterable[str] = (), limit: int = 5) -> list[str]:
    """Words most titles share, in their commonest spelling; `known` ones skipped."""
    skip = {_stem(word) for word in known}
    counts: Counter[str] = Counter()
    spellings: dict[str, Counter[str]] = {}
    order: dict[str, int] = {}
    for title in titles:
        seen: set[str] = set()
        for token in tokenize(title):
            if len(token) < 3 or token in STOPWORDS or token.isdigit():
                continue
            stem = _stem(token)
            if stem in skip:
                continue
            spellings.setdefault(stem, Counter())[token] += 1
            order.setdefault(stem, len(order))
            if stem not in seen:
                counts[stem] += 1
                seen.add(stem)
    shared = [stem for stem, count in counts.items() if count >= 2]
    shared.sort(key=lambda stem: (-counts[stem], order[stem]))
    return [spellings[stem].most_common(1)[0][0] for stem in shared[:limit]]
