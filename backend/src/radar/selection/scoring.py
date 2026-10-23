"""Pure selection logic: scoring, duplicate collapse and the final cut.

Nothing here touches the database or a model, which keeps the rules that
decide what a reader sees easy to test and to explain.
"""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import timedelta

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
# An exploited zero-day retold without its ids joins the entry with them when
# the cards name one product by two Latin words or more, within a week.
SAME_PRODUCT_NAMES = 2
SAME_PRODUCT_WINDOW = timedelta(days=7)
# Vendors and platforms with an exploited zero-day most weeks: "Microsoft
# Windows" or "Google Chrome" names no single story.
_BROAD_NAMES = frozenset(
    {"microsoft", "windows", "google", "chrome", "android", "apple", "ios", "macos", "linux"}
)
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
    # How many vulnerabilities the ids stand for, when some are aliases of
    # others: a card's CVE and the BDU id the bases tie to it are one. None
    # counts every id.
    count: int | None = None

    @property
    def size(self) -> int:
        return len(self.ids) if self.count is None else self.count


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
    if left.size <= FOCUSED_IDS and right.size <= FOCUSED_IDS:
        return True
    small, large = sorted((left, right), key=lambda mentions: mentions.size)
    return (
        small.size <= FOCUSED_IDS
        and large.size <= ROUNDUP_IDS
        and small.ids <= large.ids
        and bool(left.names & right.names)
    )


def written_mentions(item: SelectedItem) -> Mentions:
    """The ids a written vulnerability entry is about: its card's, and the BDU
    id the reference bases tie to one of its CVEs. The names are the
    headline's, as for an article."""
    text = item.text
    if text is None or text.vulnerability is None:
        return Mentions(ids=frozenset(), names=frozenset())
    named = list(text.vulnerability.ids)
    aliases = [ref.bdu_id for ref in text.references if ref.bdu_id and ref.id in named]
    own = frozenset(identifiers(" ".join(named)))
    # An alias joins the ids to meet another entry by, not the count: a card
    # of three CVEs is not a roundup because the bases gave each a BDU id.
    return Mentions(
        ids=own | frozenset(identifiers(" ".join(aliases))),
        names=_latin_words(item.article.title) or _latin_words(text.headline),
        count=len(own),
    )


def _product(item: SelectedItem) -> frozenset[str]:
    card = item.text.vulnerability if item.text else None
    return _latin_words(card.name) - _BROAD_NAMES if card is not None else frozenset()


def same_exploited_product(left: SelectedItem, right: SelectedItem) -> bool:
    """Two written entries about an exploited vulnerability of one product, one
    of them without ids, which the ids rule cannot compare: "Warning: Two
    Unpatched Citrix NetScaler RCE Zero-Days" names no CVE in the snapshot,
    the post beside it names two. Both exploited in the wild, every Latin name
    of one card's product in the other's, at least two of them ("citrix",
    "netscaler"), published within a week.

    On the snapshot of October 3, each card named by its headline's product
    words, the rule merges 17 pairs the other rules leave apart, all of them
    retellings of the Cisco Catalyst SD-WAN and Citrix NetScaler zero-days. In
    the saved digest of docs/eval/human it merges one: The Hacker News on
    Citrix into SecAtor.
    """
    a = left.text.vulnerability if left.text else None
    b = right.text.vulnerability if right.text else None
    if a is None or b is None or (a.ids and b.ids):
        return False
    if a.exploit != "in_the_wild" or b.exploit != "in_the_wild":
        return False
    small, large = sorted((_product(left), _product(right)), key=len)
    apart = abs(left.article.published_at - right.article.published_at)
    return len(small) >= SAME_PRODUCT_NAMES and small <= large and apart <= SAME_PRODUCT_WINDOW


def merge_written(
    items: Sequence[SelectedItem],
) -> tuple[list[SelectedItem], list[SelectedItem]]:
    """Two vulnerability entries that turn out to be one once their cards are
    written become one: the higher-scored stays and lists the other among its
    retellings.

    Selection merges by the ids an article prints. The cards add what it does
    not: the BDU id the bases tie to a CVE, so a Russian post that names only
    BDU:2026-15790 and an English one that names only CVE-2026-104286 meet
    here, by the thresholds of same_vulnerability; and the product of an
    exploited zero-day retold without ids (same_exploited_product). Returns
    the entries in their order and the entries merged away.
    """
    ordered = sorted(items, key=lambda item: (-item.graded.score, item.article.id))
    named = {item.article.id: written_mentions(item) for item in ordered}
    kept: list[SelectedItem] = []
    absorbed_by: dict[int, list[SelectedItem]] = {}
    absorbed: list[SelectedItem] = []
    for item in ordered:
        own = named[item.article.id]
        twin = next(
            (
                seen
                for seen in kept
                if (own.ids and same_vulnerability(own, named[seen.article.id]))
                or same_exploited_product(item, seen)
            ),
            None,
        )
        if twin is None:
            kept.append(item)
            continue
        absorbed_by.setdefault(twin.article.id, []).append(item)
        absorbed.append(item)
    position = {item.article.id: index for index, item in enumerate(items)}
    merged = [
        item.model_copy(
            update={
                "duplicates": (
                    *item.duplicates,
                    *(ref for dup in absorbed_by[item.article.id] for ref in _as_retelling(dup)),
                )
            }
        )
        if item.article.id in absorbed_by
        else item
        for item in sorted(kept, key=lambda item: position[item.article.id])
    ]
    return merged, absorbed


def _as_retelling(item: SelectedItem) -> tuple[DuplicateRef, ...]:
    """An entry merged into another: its own link, then the ones it had merged."""
    article = item.article
    own = DuplicateRef(title=article.title, url=article.url, source_name=article.source_name)
    return (own, *item.duplicates)


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
