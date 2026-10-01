"""A reader's taste as a set of facets. Pure: no database, no model calls."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from sklearn.cluster import AgglomerativeClustering

from radar.recsys.signals import REJECTING, decayed_weight

FacetKind = Literal["interest", "resume", "learned", "avoid"]

# One centroid per this many signals, within the caps below. A reader who
# liked twelve articles on three subjects gets three facets, not one blurred
# average of them.
_SIGNALS_PER_FACET = 4
MAX_LEARNED_FACETS = 4
MAX_AVOID_FACETS = 3
# Total signal weight at which behaviour is trusted as much as it ever is.
_FULL_CONFIDENCE = 6.0
# Signals from one source needed before its affinity counts in full.
_SOURCE_CONFIDENCE = 5.0


@dataclass(frozen=True, slots=True)
class Signal:
    """One reader signal, joined with what is needed from the article."""

    article_id: int
    kind: str
    age_days: float
    source_id: int
    title: str
    vector: np.ndarray | None = None


@dataclass(frozen=True, slots=True)
class Facet:
    key: str
    kind: FacetKind
    # Shown to the reader as the reason an article was recommended.
    label: str
    vector: np.ndarray | None = None
    # Importance relative to other facets of the same kind.
    weight: float = 1.0
    # Full-text query for the facet, empty when it has none.
    query: str = ""


@dataclass(frozen=True, slots=True)
class Taste:
    facets: tuple[Facet, ...] = ()
    # source id -> preference in -0.5..0.5
    source_affinity: dict[int, float] = field(default_factory=dict)
    # article id -> kinds of signals the reader gave it (recent ones)
    reactions: dict[int, frozenset[str]] = field(default_factory=dict)
    # Every article the reader ever disliked or hid, however old: a hidden
    # article must not come back once newer signals push it out of the
    # window the taste is learned from.
    rejected_ids: frozenset[int] = frozenset()
    # 0 with no behaviour on record, 1 once there is plenty.
    confidence: float = 0.0
    positives: int = 0
    negatives: int = 0

    def of_kind(self, kind: FacetKind) -> tuple[Facet, ...]:
        return tuple(facet for facet in self.facets if facet.kind == kind)

    def rejected(self, article_id: int) -> bool:
        return article_id in self.rejected_ids or bool(
            self.reactions.get(article_id, frozenset()) & REJECTING
        )

    def centroid(self) -> np.ndarray | None:
        """One vector for the whole taste, used to find readers alike."""
        vectors = [
            facet.vector * facet.weight
            for facet in self.facets
            if facet.kind != "avoid" and facet.vector is not None
        ]
        if not vectors:
            return None
        return _unit(np.sum(vectors, axis=0))


def _unit(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm else vector


def net_weights(signals: Sequence[Signal]) -> dict[int, tuple[float, Signal]]:
    """Sum the signals of one article into a single signed weight.

    An article that was opened and then disliked is a rejection, not half a
    recommendation: the strongest negative signal wins.
    """
    by_article: dict[int, list[Signal]] = {}
    for signal in signals:
        by_article.setdefault(signal.article_id, []).append(signal)
    net: dict[int, tuple[float, Signal]] = {}
    for article_id, items in by_article.items():
        weights = [decayed_weight(item.kind, item.age_days) for item in items]
        negative = min(weights)
        total = negative if negative < 0 else sum(weights)
        net[article_id] = (total, items[0])
    return net


def cluster_labels(vectors: np.ndarray, max_clusters: int) -> np.ndarray:
    count = len(vectors)
    clusters = min(max_clusters, max(1, count // _SIGNALS_PER_FACET))
    if clusters == 1:
        return np.zeros(count, dtype=int)
    # Ward linkage on unit vectors, as for digest topics: compact groups of
    # comparable size rather than one large group and a few strays.
    labels: np.ndarray = AgglomerativeClustering(n_clusters=clusters, linkage="ward").fit_predict(
        vectors
    )
    return labels


def _learn(
    weighted: Sequence[tuple[float, Signal]], kind: FacetKind, max_clusters: int
) -> list[Facet]:
    """Group signals into facets: one weighted centroid per theme."""
    usable = [
        (weight, signal, signal.vector) for weight, signal in weighted if signal.vector is not None
    ]
    if not usable:
        return []
    labels = cluster_labels(np.stack([vector for _, _, vector in usable]), max_clusters)
    total = sum(weight for weight, _, _ in usable)
    facets = []
    for label in sorted(set(labels.tolist())):
        members = [item for item, owner in zip(usable, labels, strict=True) if owner == label]
        mass = sum(weight for weight, _, _ in members)
        centroid = _unit(
            np.sum(np.stack([weight * vector for weight, _, vector in members]), axis=0)
        )
        anchor = max(members, key=lambda item: item[0])[1]
        facets.append(
            Facet(
                key=f"{kind}:{anchor.article_id}",
                kind=kind,
                # The strongest article of the group names it for the reader.
                label=anchor.title,
                vector=centroid,
                weight=mass / total if total else 1.0,
            )
        )
    # Express weights relative to the heaviest facet, so the main theme of the
    # reader counts in full whatever the number of themes.
    top = max(facet.weight for facet in facets)
    return [
        Facet(facet.key, facet.kind, facet.label, facet.vector, facet.weight / top)
        for facet in sorted(facets, key=lambda facet: -facet.weight)
    ]


def _source_affinity(net: dict[int, tuple[float, Signal]]) -> dict[int, float]:
    """Preference per source, shrunk towards neutral while evidence is thin.

    The posterior mean of a Beta(1, 1) prior: three likes out of three move a
    source less than thirty out of thirty.
    """
    liked: dict[int, float] = {}
    rejected: dict[int, float] = {}
    for weight, signal in net.values():
        bucket = liked if weight > 0 else rejected
        bucket[signal.source_id] = bucket.get(signal.source_id, 0.0) + abs(weight)
    affinity = {}
    for source_id in liked.keys() | rejected.keys():
        up, down = liked.get(source_id, 0.0), rejected.get(source_id, 0.0)
        mean = (up + 1.0) / (up + down + 2.0) - 0.5
        affinity[source_id] = mean * min(1.0, (up + down) / _SOURCE_CONFIDENCE)
    return affinity


def build_taste(
    declared: Sequence[Facet],
    signals: Sequence[Signal],
    rejected_ids: frozenset[int] = frozenset(),
) -> Taste:
    """Combine what the reader stated (interests, resume) with what they did."""
    net = net_weights(signals)
    positive = [(weight, signal) for weight, signal in net.values() if weight > 0]
    negative = [(-weight, signal) for weight, signal in net.values() if weight < 0]
    reactions: dict[int, set[str]] = {}
    for signal in signals:
        reactions.setdefault(signal.article_id, set()).add(signal.kind)
    return Taste(
        facets=(
            *declared,
            *_learn(positive, "learned", MAX_LEARNED_FACETS),
            *_learn(negative, "avoid", MAX_AVOID_FACETS),
        ),
        source_affinity=_source_affinity(net),
        reactions={article_id: frozenset(kinds) for article_id, kinds in reactions.items()},
        rejected_ids=rejected_ids,
        confidence=min(1.0, sum(weight for weight, _ in positive) / _FULL_CONFIDENCE),
        positives=len(positive),
        negatives=len(negative),
    )
