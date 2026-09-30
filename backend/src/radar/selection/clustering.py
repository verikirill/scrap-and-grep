"""Group selected items into topics by embedding similarity."""

from collections.abc import Sequence

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score

from radar.domain import SelectedItem

MIN_ITEMS_TO_CLUSTER = 4
MAX_TOPICS = 7


def cluster_items(
    items: Sequence[SelectedItem], vectors: dict[int, np.ndarray], *, semantic: bool = True
) -> list[list[SelectedItem]]:
    """Split items into topics, most important topic first.

    The number of topics is chosen by silhouette score rather than a distance
    threshold, because a threshold would have to be re-tuned for every
    embedding model. When the vectors carry no meaning (the offline embedder) or
    are missing, items are grouped by the interest that selected them.
    """
    clusterable = semantic and len(items) >= MIN_ITEMS_TO_CLUSTER
    if not clusterable or any(item.article.id not in vectors for item in items):
        return _order(_group_by_interest(items))

    matrix = np.vstack([vectors[item.article.id] for item in items])
    labels = _best_labels(matrix)
    groups: dict[int, list[SelectedItem]] = {}
    for item, label in zip(items, labels, strict=True):
        groups.setdefault(int(label), []).append(item)
    return _order(list(groups.values()))


def _best_labels(matrix: np.ndarray) -> np.ndarray:
    upper = min(MAX_TOPICS, len(matrix) - 1)
    best_labels = np.zeros(len(matrix), dtype=int)
    best_quality = -1.0
    for count in range(2, upper + 1):
        labels = AgglomerativeClustering(
            n_clusters=count, metric="cosine", linkage="average"
        ).fit_predict(matrix)
        quality = float(silhouette_score(matrix, labels, metric="cosine"))
        # A split that leaves most items alone in their topic is not a grouping.
        singletons = int(np.sum(np.bincount(labels) == 1))
        if singletons > count // 2:
            continue
        if quality > best_quality:
            best_quality, best_labels = quality, labels
    return best_labels


def _group_by_interest(items: Sequence[SelectedItem]) -> list[list[SelectedItem]]:
    groups: dict[str, list[SelectedItem]] = {}
    for item in items:
        groups.setdefault(item.graded.interest_id, []).append(item)
    return list(groups.values())


def _order(groups: list[list[SelectedItem]]) -> list[list[SelectedItem]]:
    sorted_groups = [
        sorted(group, key=lambda item: (-item.graded.score, item.article.id)) for group in groups
    ]
    return sorted(
        sorted_groups,
        key=lambda group: (-max(item.graded.score for item in group), -len(group)),
    )
