"""Group selected items into topics by embedding similarity."""

from collections.abc import Sequence

import numpy as np
from sklearn.cluster import AgglomerativeClustering

from radar.domain import SelectedItem

MIN_ITEMS_TO_CLUSTER = 4
MAX_TOPICS = 6
# A topic of about five entries reads well; fewer topics hide the structure,
# more turn the digest into a list of headings.
ITEMS_PER_TOPIC = 5


def cluster_items(
    items: Sequence[SelectedItem], vectors: dict[int, np.ndarray], *, semantic: bool = True
) -> list[list[SelectedItem]]:
    """Split items into topics, most important topic first.

    Ward linkage on unit vectors, with the number of topics taken from the
    size of the digest. The first version chose the number by silhouette score
    with average linkage; on real digests that split 20 items into 18 and 2,
    because one broad theme plus two outliers is what the score rewards. Ward
    keeps topics balanced, and the same three digests came out as 6+6+4+4.

    When the vectors carry no meaning (the offline embedder) or are missing,
    items are grouped by the interest that selected them.
    """
    clusterable = semantic and len(items) >= MIN_ITEMS_TO_CLUSTER
    if not clusterable or any(item.article.id not in vectors for item in items):
        return _order(_group_by_interest(items))

    matrix = np.vstack([vectors[item.article.id] for item in items]).astype(np.float64)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    labels = _topic_labels(matrix / np.where(norms == 0, 1.0, norms))
    groups: dict[int, list[SelectedItem]] = {}
    for item, label in zip(items, labels, strict=True):
        groups.setdefault(int(label), []).append(item)
    return _order(list(groups.values()))


def _topic_labels(matrix: np.ndarray) -> np.ndarray:
    count = max(2, min(MAX_TOPICS, len(matrix) // 2, round(len(matrix) / ITEMS_PER_TOPIC)))
    while True:
        labels = AgglomerativeClustering(n_clusters=count, linkage="ward").fit_predict(matrix)
        # A topic of one entry is not a topic; try a coarser split instead.
        if count == 2 or int(np.bincount(labels).min()) > 1:
            return np.asarray(labels)
        count -= 1


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
