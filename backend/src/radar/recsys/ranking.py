"""Turn evidence into a ranked feed. Pure: no database, no model calls."""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np

from radar.recsys.taste import Facet, Taste
from radar.selection.scoring import lexical_score, retrieval_score

# Every this-many-th place in the feed goes to an article the reader's taste
# would not have picked. Without it a feed only confirms what it already
# knows, and a reader never gets the chance to show a new interest.
EXPLORE_EVERY = 7
# How far back the variety re-rank looks when it counts articles of one source.
_SOURCE_WINDOW = 8
_SOURCE_REPEAT_PENALTY = 0.04
# Freshness halves every two days: a week-old article competes on relevance alone.
FRESH_HALF_LIFE_HOURS = 48.0
# Closeness to a rejected theme starts to count one deviation above the
# period's average and is in full force at five.
_AVOID_FROM_Z = 1.0
_AVOID_PER_Z = 0.25


@dataclass(frozen=True, slots=True)
class Weights:
    """How the parts of the evidence are blended. Tuned on the project's own
    data with `scripts/eval_recsys.py`; see docs/DECISIONS.md."""

    # Trust in each kind of evidence. The interest weight is the unit; the
    # grid search found the resume worth under a quarter of a stated interest.
    interest: float = 0.45
    resume: float = 0.10
    learned: float = 0.35
    # Share of the best single match against the weighted average of all of
    # them. 1.0 would ignore agreement between facets, 0.0 would punish an
    # article that fits one interest perfectly and the others not at all.
    peak: float = 0.3
    fresh: float = 0.10
    source: float = 0.08
    collab: float = 0.07
    avoid: float = 0.2
    read_penalty: float = 0.15
    # Below this an article is not recommended at all.
    min_score: float = 0.35
    # Relevance against variety in the re-rank: 1.0 is pure relevance. Kept
    # light: measured, every step towards variety cost relevance and bought
    # little (docs/DECISIONS.md). The pass still drops copies of one story and
    # breaks up runs of one source.
    variety: float = 0.95


@dataclass(frozen=True, slots=True)
class Evidence:
    """Everything the score of one article is computed from."""

    article_id: int
    source_id: int
    age_hours: float
    # facet key -> similarity to the facet, in deviations from the period's mean
    z: dict[str, float] = field(default_factory=dict)
    # facet key -> full-text rank relative to the facet's best match
    rank_share: dict[str, float] = field(default_factory=dict)
    # What readers with a similar taste did with the article, 0..1.
    collab: float = 0.0


@dataclass(frozen=True, slots=True)
class Ranked:
    article_id: int
    score: float
    # Contribution of each part, for the "why is this here" explanation.
    parts: dict[str, float]
    # Facet that matched best, per facet kind.
    best: dict[str, str]
    explore: bool = False


def _match(evidence: Evidence, facet: Facet, *, semantic: bool) -> float:
    z = evidence.z.get(facet.key, 0.0)
    share = evidence.rank_share.get(facet.key)
    hit = share is not None
    if semantic and facet.key in evidence.z:
        return retrieval_score(z, hit)
    # An embedder that only sees spelling, or an article without a vector:
    # a keyword match is then the evidence that counts.
    if facet.query:
        return lexical_score(share or 0.0, z, hit)
    # Learned facets have no keywords; spelling closeness is all there is.
    return retrieval_score(z, False)


def _best(
    evidence: Evidence, facets: Sequence[Facet], *, semantic: bool
) -> tuple[float, str | None]:
    best_value, best_key = 0.0, None
    for facet in facets:
        value = min(1.0, _match(evidence, facet, semantic=semantic) * facet.weight)
        if value > best_value:
            best_value, best_key = value, facet.key
    return best_value, best_key


def freshness(age_hours: float) -> float:
    return float(0.5 ** (max(0.0, age_hours) / FRESH_HALF_LIFE_HOURS))


def score_article(
    evidence: Evidence, taste: Taste, weights: Weights, *, semantic: bool, read: bool = False
) -> Ranked:
    """Blend the evidence about one article into a score in 0..1."""
    interest, interest_key = _best(evidence, taste.of_kind("interest"), semantic=semantic)
    resume, resume_key = _best(evidence, taste.of_kind("resume"), semantic=semantic)
    learned, learned_key = _best(evidence, taste.of_kind("learned"), semantic=semantic)

    # Behaviour earns its weight: with two likes on record a learned theme is
    # a hint, with a dozen it is as trustworthy as a stated interest.
    active = {
        "interest": weights.interest if taste.of_kind("interest") else 0.0,
        "resume": weights.resume if taste.of_kind("resume") else 0.0,
        "learned": weights.learned * taste.confidence if taste.of_kind("learned") else 0.0,
    }
    values = {"interest": interest, "resume": resume, "learned": learned}
    total = sum(active.values())
    if total:
        average = sum(active[name] * values[name] for name in active) / total
        # The best match counts in proportion to how far its kind is trusted:
        # a resume is a rougher description of a reader than a stated
        # interest, so a resume match alone cannot outrank an interest match
        # of the same strength.
        most_trusted = max(active.values())
        peak = max(values[name] * active[name] / most_trusted for name in active)
        relevance = weights.peak * peak + (1 - weights.peak) * average
    else:
        relevance = 0.0

    avoid = 0.0
    for facet in taste.of_kind("avoid"):
        closeness = _AVOID_PER_Z * (evidence.z.get(facet.key, 0.0) - _AVOID_FROM_Z)
        avoid = max(avoid, min(1.0, max(0.0, closeness)) * facet.weight)

    parts = {
        "relevance": relevance,
        "fresh": weights.fresh * (freshness(evidence.age_hours) - 0.5),
        "source": weights.source * 2 * taste.source_affinity.get(evidence.source_id, 0.0),
        "collab": weights.collab * min(1.0, evidence.collab),
        "avoid": -weights.avoid * avoid,
        "read": -weights.read_penalty if read else 0.0,
    }
    best = {
        kind: key
        for kind, key in (
            ("interest", interest_key),
            ("resume", resume_key),
            ("learned", learned_key),
        )
        if key is not None
    }
    parts.update({"interest": interest, "resume": resume, "learned": learned})
    score = sum(parts[name] for name in ("relevance", "fresh", "source", "collab", "avoid", "read"))
    return Ranked(
        article_id=evidence.article_id,
        score=float(min(1.0, max(0.0, score))),
        parts={name: round(float(value), 4) for name, value in parts.items()},
        best=best,
    )


def rerank_for_variety(
    ranked: Sequence[Ranked],
    vectors: dict[int, np.ndarray],
    sources: dict[int, int],
    *,
    duplicate_threshold: float,
    variety: float,
    limit: int,
) -> list[Ranked]:
    """Greedy maximal-marginal-relevance pass over an already scored list.

    Each pick maximises relevance minus closeness to what is already in the
    feed, so five reports on one incident do not fill the first screen. A
    near-copy of a chosen article (above the embedder's duplicate threshold)
    is dropped outright.
    """
    pool = sorted(ranked, key=lambda item: (-item.score, item.article_id))
    if not pool:
        return []
    width = next((len(vector) for vector in vectors.values()), 1)
    blank = np.zeros(width, dtype=np.float32)
    # An article without a vector is compared as a zero vector: similar to nothing.
    matrix = np.stack([vectors.get(item.article_id, blank) for item in pool])
    scores = np.array([item.score for item in pool])
    source_of = [sources.get(item.article_id) for item in pool]
    closest = np.zeros(len(pool))
    alive = np.ones(len(pool), dtype=bool)
    chosen: list[Ranked] = []
    recent: list[int | None] = []
    while alive.any() and len(chosen) < limit:
        repeats = np.array([recent[-_SOURCE_WINDOW:].count(source) for source in source_of])
        value = variety * scores - (1 - variety) * closest - _SOURCE_REPEAT_PENALTY * repeats
        value[~alive] = -np.inf
        index = int(np.argmax(value))
        chosen.append(pool[index])
        recent.append(source_of[index])
        alive[index] = False
        closest = np.maximum(closest, matrix @ matrix[index])
        alive &= closest < duplicate_threshold
    return chosen


def _stable_noise(seed: str, article_id: int) -> float:
    """A number in 0..1 that is fixed for a reader, a day and an article.

    Exploration picks must not reshuffle on every page load, and they must
    differ between readers and between days.
    """
    digest = hashlib.sha256(f"{seed}:{article_id}".encode()).digest()
    return int.from_bytes(digest[:4], "big") / 0xFFFFFFFF


def with_exploration(
    feed: Sequence[Ranked], candidates: Sequence[Ranked], *, seed: str, limit: int
) -> list[Ranked]:
    """Put an exploration pick on every `EXPLORE_EVERY`-th place.

    Candidates are articles the taste did not select. Among them, fresh ones
    that are not close to anything the reader rejected are preferred.
    """
    taken = {item.article_id for item in feed}
    spare = sorted(
        (item for item in candidates if item.article_id not in taken and item.parts["avoid"] == 0),
        key=lambda item: -(item.parts["fresh"] + 0.1 * _stable_noise(seed, item.article_id)),
    )
    result: list[Ranked] = []
    main = list(feed)
    while main and len(result) < limit:
        if spare and (len(result) + 1) % EXPLORE_EVERY == 0:
            pick = spare.pop(0)
            result.append(Ranked(pick.article_id, pick.score, pick.parts, pick.best, explore=True))
            continue
        result.append(main.pop(0))
    return result
