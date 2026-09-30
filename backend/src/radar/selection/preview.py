"""Instant selection preview: retrieval evidence only, no language model.

The profile editor calls this on every change, so the reader sees which
articles a tweak would bring in or push out before paying for a full digest.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from radar.ai.embedder import Embedder
from radar.domain import Candidate, Grade, GradedCandidate, ProfileSpec
from radar.logging import get_logger
from radar.pipeline.ports import QueryEmbedder
from radar.selection.retrieval import Window, retrieve_candidates
from radar.selection.scoring import grade_with, rank_candidates, relevance_from_score, select
from radar.store.articles import load_vectors

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Preview:
    window_total: int
    lexical_only: bool
    graded: list[GradedCandidate]
    selected_ids: set[int]
    rejected: dict[int, str]


def _retrieval_verdict(candidate: Candidate) -> Grade:
    return Grade(
        relevance=relevance_from_score(candidate.retrieval_score),
        interest_id=candidate.interest_id,
    )


async def build_preview(
    session: AsyncSession,
    *,
    profile: ProfileSpec,
    start: datetime,
    end: datetime,
    embedder: Embedder,
    embed_queries: QueryEmbedder,
    per_interest_limit: int,
    candidate_limit: int,
) -> Preview:
    window = Window(
        start=start, end=end, languages=profile.languages, categories=profile.categories
    )
    interest_vectors: dict[str, list[float]] | None = None
    exclusion_vectors: dict[str, list[float]] | None = None
    try:
        texts = [interest.as_query() for interest in profile.interests]
        vectors = await embed_queries([*texts, *profile.exclusions])
        interest_vectors = {
            interest.id: vector
            for interest, vector in zip(profile.interests, vectors, strict=False)
        }
        exclusion_vectors = dict(
            zip(profile.exclusions, vectors[len(profile.interests) :], strict=True)
        )
    except Exception as exc:
        log.warning("preview_embedding_failed", error=f"{type(exc).__name__}: {exc}"[:300])

    candidates, total = await retrieve_candidates(
        session,
        model=embedder.model_id,
        profile=profile,
        window=window,
        interest_vectors=interest_vectors,
        exclusion_vectors=exclusion_vectors,
        per_interest_limit=per_interest_limit,
        semantic=embedder.semantic,
    )
    ranked = rank_candidates(candidates, candidate_limit)
    graded = grade_with(ranked, profile, _retrieval_verdict)
    article_vectors = await load_vectors(
        session, embedder.model_id, [item.article.id for item in graded]
    )
    selected, rejected = select(graded, profile, article_vectors, embedder.duplicate_threshold)
    return Preview(
        window_total=total,
        lexical_only=interest_vectors is None,
        graded=sorted(graded, key=lambda item: -item.score),
        selected_ids={item.article.id for item in selected},
        rejected=rejected,
    )
