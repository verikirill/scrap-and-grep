"""Pure selection logic: scoring, duplicate collapse and the final cut.

Nothing here touches the database or a model, which keeps the rules that
decide what a reader sees easy to test and to explain.
"""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

from radar.cards import identifiers
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
# Two publications that name the same CVE or BDU entry, each naming a few,
# report one vulnerability. A roundup of thirty is not one story with each of
# them: it joins one only when it names all of that one's ids and the two
# headlines share a Latin name ("Kiteworks").
FOCUSED_IDS = 4
ROUNDUP_IDS = 12
# A post with no Latin word in its first line ("Ирония судьбы") is named by
# the start of its text.
_NAMES_FROM_TEXT = 300
_ID_WORDS_RE = re.compile(r"\b(?:CVE|BDU|БДУ|GHSA)[-:\s]*[\w-]*", re.IGNORECASE)

REJECT_LOW_SCORE = "low_score"
REJECT_EXCLUDED = "excluded"
REJECT_DUPLICATE = "duplicate"
REJECT_OVER_LIMIT = "over_limit"
REJECT_HIDDEN = "hidden"


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
    Among the matches, full-text rank decides and n-gram closeness only breaks
    ties: given more weight it made the ranking worse than full-text search
    alone (recall@60 0.27 against 0.34 on a week of articles, docs/eval).
    """
    closeness = min(4.0, max(0.0, z_score))
    if not lexical_hit:
        return float(min(NO_KEYWORD_CEILING, 0.2 + 0.06 * closeness))
    return float(min(1.0, 0.5 + 0.46 * rank_share + 0.01 * closeness))


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
    named = {
        item.article.id: mentions(item.article.title, item.article.summary, item.article.content)
        for item in ordered
    }
    kept: list[GradedCandidate] = []
    absorbed_by: dict[int, list[GradedCandidate]] = {}
    absorbed: list[GradedCandidate] = []
    for item in ordered:
        twin = next(
            (seen for seen in kept if _same_story(item, seen, vectors, threshold, named)), None
        )
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


@dataclass(frozen=True, slots=True)
class Mentions:
    """The vulnerability ids a publication names, and the Latin words of its
    headline: product and vendor names, which Russian and English titles of
    one advisory write alike."""

    ids: frozenset[str]
    names: frozenset[str]


def _latin_words(text: str) -> frozenset[str]:
    # The ids themselves are not names: every title that prints one has "cve".
    bare = _ID_WORDS_RE.sub(" ", text)
    return frozenset(
        word for word in content_tokens(bare) if any("a" <= char <= "z" for char in word)
    )


def mentions(title: str, summary: str, content: str | None) -> Mentions:
    ids = frozenset(identifiers(f"{title}\n{summary}\n{content or ''}"))
    names = _latin_words(title) or _latin_words(summary[:_NAMES_FROM_TEXT])
    return Mentions(ids=ids, names=names)


def same_vulnerability(left: Mentions, right: Mentions) -> bool:
    """Two publications about one vulnerability: a CVE or BDU id in common,
    each naming a few. A roundup joins one only when it names all of that
    one's ids and their headlines share a name.

    Asking every pair for a shared name lost more than it saved: on the
    snapshot of October 3 it kept apart 20 retellings of one event whose
    headlines name none ("Ирония судьбы", "В продолжение к предыдущему",
    "Certainties in life...") to keep apart 2 pairs that were not one.
    """
    if not left.ids & right.ids:
        return False
    if len(left.ids) <= FOCUSED_IDS and len(right.ids) <= FOCUSED_IDS:
        return True
    small, large = sorted((left.ids, right.ids), key=len)
    return (
        len(small) <= FOCUSED_IDS
        and len(large) <= ROUNDUP_IDS
        and small <= large
        and bool(left.names & right.names)
    )


def _same_story(
    left: GradedCandidate,
    right: GradedCandidate,
    vectors: dict[int, np.ndarray],
    threshold: float,
    named: dict[int, Mentions] | None = None,
) -> bool:
    if left.article.content_hash == right.article.content_hash:
        return True
    if _same_headline(left.article.title, right.article.title):
        return True
    if named is not None and same_vulnerability(named[left.article.id], named[right.article.id]):
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
        if item.rejected_by_reader:
            rejected[item.article.id] = REJECT_HIDDEN
        elif item.candidate.excluded_by is not None:
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
