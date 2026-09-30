"""Pure selection logic: scoring, duplicate collapse and the final cut.

Nothing here touches the database or a model, which keeps the rules that
decide what a reader sees easy to test and to explain.
"""

from collections.abc import Callable, Sequence

import numpy as np

from radar.domain import (
    Candidate,
    DuplicateRef,
    Grade,
    GradedCandidate,
    ProfileSpec,
    SelectedItem,
)
from radar.text import content_tokens

# A model verdict of 0..3 mapped onto the 0..1 score scale.
RELEVANCE_TO_SCORE = (0.0, 0.35, 0.7, 1.0)
MODEL_WEIGHT = 0.7
LEXICAL_BONUS = 0.12
NO_KEYWORD_CEILING = 0.45
TITLE_JACCARD_DUPLICATE = 0.6
TITLE_MIN_SHARED_WORDS = 3

REJECT_LOW_SCORE = "low_score"
REJECT_EXCLUDED = "excluded"
REJECT_DUPLICATE = "duplicate"
REJECT_OVER_LIMIT = "over_limit"


def retrieval_score(z_score: float, lexical_hit: bool) -> float:
    """Turn "how unusual is this similarity" into a 0..1 score.

    Raw cosine values are not comparable between embedding models: one packs
    everything into 0.4-0.7, another into 0.0-0.3. The z-score against the
    whole period is, so the threshold in a profile keeps its meaning when the
    model changes.
    """
    base = 0.2 + 0.18 * z_score
    if lexical_hit:
        base += LEXICAL_BONUS
    return float(min(1.0, max(0.0, base)))


def lexical_score(rank_share: float, z_score: float, lexical_hit: bool) -> float:
    """Score for embedders that only see spelling, and for lexical-only search.

    Without semantic similarity a keyword match is the only trustworthy
    evidence, so an article with no match stays below any sensible threshold.
    Among the matches, full-text rank leads and n-gram closeness breaks ties.
    """
    closeness = min(4.0, max(0.0, z_score))
    if not lexical_hit:
        return float(min(NO_KEYWORD_CEILING, 0.2 + 0.06 * closeness))
    return float(min(1.0, 0.5 + 0.3 * rank_share + 0.05 * closeness))


def relevance_from_score(score: float) -> int:
    """Inverse of RELEVANCE_TO_SCORE for the heuristic grader."""
    if score >= 0.78:
        return 3
    if score >= 0.5:
        return 2
    if score >= 0.3:
        return 1
    return 0


def final_score(candidate: Candidate, grade: Grade, weight: float) -> float:
    """Blend the model verdict with retrieval evidence, then apply interest weight."""
    if grade.by_model:
        base = (
            MODEL_WEIGHT * RELEVANCE_TO_SCORE[grade.relevance]
            + (1 - MODEL_WEIGHT) * candidate.retrieval_score
        )
    else:
        base = candidate.retrieval_score
    return float(min(1.0, base * weight))


def rank_candidates(candidates: Sequence[Candidate], limit: int) -> list[Candidate]:
    """Keep the best interest match per article and cap the pool."""
    best: dict[int, Candidate] = {}
    for candidate in candidates:
        current = best.get(candidate.article.id)
        if current is None or candidate.retrieval_score > current.retrieval_score:
            best[candidate.article.id] = candidate
    ranked = sorted(best.values(), key=lambda item: (-item.retrieval_score, item.article.id))
    return ranked[:limit]


def _same_headline(left: str, right: str) -> bool:
    """Headlines that share most of their words, and enough of them to mean it.

    The minimum overlap matters: "Обновление Chrome" and "Обновление Firefox"
    share half of their words and are still different news.
    """
    a, b = set(content_tokens(left)), set(content_tokens(right))
    shared = len(a & b)
    return shared >= TITLE_MIN_SHARED_WORDS and shared / len(a | b) >= TITLE_JACCARD_DUPLICATE


def collapse_duplicates(
    graded: Sequence[GradedCandidate],
    vectors: dict[int, np.ndarray],
    threshold: float,
) -> tuple[list[SelectedItem], list[GradedCandidate]]:
    """Merge retellings of one story, keeping the highest-scored version.

    Returns the surviving items (each carrying links to the versions it
    absorbed) and the list of absorbed candidates.
    """
    ordered = sorted(graded, key=lambda item: (-item.score, item.article.id))
    kept: list[GradedCandidate] = []
    absorbed_by: dict[int, list[GradedCandidate]] = {}
    absorbed: list[GradedCandidate] = []
    for item in ordered:
        twin = next((seen for seen in kept if _same_story(item, seen, vectors, threshold)), None)
        if twin is None:
            kept.append(item)
            continue
        absorbed_by.setdefault(twin.article.id, []).append(item)
        absorbed.append(item)
    selected = [
        SelectedItem(
            graded=item,
            duplicates=tuple(
                DuplicateRef(
                    title=dup.article.title,
                    url=dup.article.url,
                    source_name=dup.article.source_name,
                )
                for dup in absorbed_by.get(item.article.id, [])
            ),
        )
        for item in kept
    ]
    return selected, absorbed


def _same_story(
    left: GradedCandidate,
    right: GradedCandidate,
    vectors: dict[int, np.ndarray],
    threshold: float,
) -> bool:
    if left.article.content_hash == right.article.content_hash:
        return True
    if _same_headline(left.article.title, right.article.title):
        return True
    a, b = vectors.get(left.article.id), vectors.get(right.article.id)
    if a is None or b is None:
        return False
    return float(np.dot(a, b)) >= threshold


def select(
    graded: Sequence[GradedCandidate],
    profile: ProfileSpec,
    vectors: dict[int, np.ndarray],
    duplicate_threshold: float,
) -> tuple[list[SelectedItem], dict[int, str]]:
    """Apply exclusions, the score threshold, duplicate collapse and the size cap.

    Returns selected items ordered by score and a rejection reason for every
    candidate that did not make it.
    """
    rejected: dict[int, str] = {}
    passing: list[GradedCandidate] = []
    for item in graded:
        if item.candidate.excluded_by is not None:
            rejected[item.article.id] = REJECT_EXCLUDED
        elif item.score < profile.min_score:
            rejected[item.article.id] = REJECT_LOW_SCORE
        else:
            passing.append(item)
    unique, absorbed = collapse_duplicates(passing, vectors, duplicate_threshold)
    for duplicate in absorbed:
        rejected[duplicate.article.id] = REJECT_DUPLICATE
    for overflow in unique[profile.max_items :]:
        rejected[overflow.article.id] = REJECT_OVER_LIMIT
    return unique[: profile.max_items], rejected


def grade_with(
    candidates: Sequence[Candidate],
    profile: ProfileSpec,
    verdict: Callable[[Candidate], Grade],
) -> list[GradedCandidate]:
    """Attach verdicts and final scores; used by the preview and by tests."""
    result = []
    for candidate in candidates:
        grade = verdict(candidate)
        interest = profile.interest(grade.interest_id or candidate.interest_id)
        weight = interest.weight if interest else 1.0
        result.append(
            GradedCandidate(
                candidate=candidate, grade=grade, score=final_score(candidate, grade, weight)
            )
        )
    return result
