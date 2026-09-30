"""Candidate retrieval: dense similarity plus full-text search, per interest."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from radar.config import EMBEDDING_DIM
from radar.domain import Candidate, ProfileSpec
from radar.selection.scoring import lexical_score, retrieval_score
from radar.store.articles import get_refs
from radar.text import tokenize

# An exclusion removes an article only when it matches clearly and at least as
# well as the interest that brought the article in.
EXCLUSION_MIN_SCORE = 0.6

# The window is scanned exactly: every article published in the period gets a
# similarity, which also yields the mean and deviation needed for the z-score.
# With tens of thousands of rows per window this takes milliseconds. Past a few
# hundred thousand the dense leg should switch to the HNSW index with an
# iterative scan and the statistics to a sample.
_RETRIEVE_SQL = text(
    """
    WITH scope AS (
        SELECT a.id, a.search_tsv, e.embedding
        FROM articles a
        JOIN sources s ON s.id = a.source_id
        LEFT JOIN article_embeddings e ON e.article_id = a.id AND e.model = :model
        WHERE a.published_at >= :start AND a.published_at < :end
          AND a.language = ANY(:languages)
          AND (:any_category OR s.category = ANY(:categories))
    ),
    sims AS (
        SELECT id, 1 - (embedding <=> CAST(:query_vector AS vector)) AS sim
        FROM scope
        WHERE embedding IS NOT NULL AND CAST(:has_vector AS boolean)
    ),
    stats AS (
        SELECT avg(sim) AS mean, stddev_pop(sim) AS std FROM sims
    ),
    dense AS (
        SELECT id FROM sims ORDER BY sim DESC LIMIT :limit
    ),
    lexical AS (
        SELECT scope.id, ts_rank_cd(scope.search_tsv, query) AS rank
        FROM scope, websearch_to_tsquery('russian', :query_text) AS query
        WHERE :query_text <> '' AND scope.search_tsv @@ query
        ORDER BY rank DESC
        LIMIT :limit
    ),
    pool AS (
        SELECT id FROM dense UNION SELECT id FROM lexical
    )
    SELECT pool.id,
           sims.sim,
           lexical.rank,
           max(lexical.rank) OVER () AS max_rank,
           stats.mean,
           stats.std
    FROM pool
    LEFT JOIN sims USING (id)
    LEFT JOIN lexical USING (id)
    CROSS JOIN stats
    """
)


@dataclass(frozen=True, slots=True)
class Window:
    start: datetime
    end: datetime
    languages: tuple[str, ...]
    categories: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Hit:
    article_id: int
    similarity: float
    z_score: float
    lexical_hit: bool
    score: float


def keyword_query(keywords: tuple[str, ...] | list[str]) -> str:
    """Build a websearch query: any keyword matches, multi-word ones as phrases."""
    terms = []
    for keyword in keywords:
        tokens = tokenize(keyword)
        if not tokens:
            continue
        terms.append(tokens[0] if len(tokens) == 1 else '"' + " ".join(tokens) + '"')
    return " OR ".join(dict.fromkeys(terms))


def _excluded_by(match: tuple[str, float] | None, interest_score: float) -> str | None:
    """The exclusion wins only when it fits at least as well as the interest."""
    if match is None or match[1] < interest_score:
        return None
    return match[0]


def _vector_literal(vector: list[float] | None) -> str:
    if vector is None:
        # Never compared (has_vector is false), but it must still parse as a
        # vector of the stored width.
        return "[" + ",".join(["0"] * EMBEDDING_DIM) + "]"
    return "[" + ",".join(f"{value:.6f}" for value in vector) + "]"


async def search(
    session: AsyncSession,
    *,
    model: str,
    window: Window,
    query_vector: list[float] | None,
    query_text: str,
    limit: int,
    semantic: bool = True,
) -> list[Hit]:
    """Run one hybrid query. `query_vector=None` degrades to lexical search only."""
    result = await session.execute(
        _RETRIEVE_SQL,
        {
            "model": model,
            "start": window.start,
            "end": window.end,
            "languages": list(window.languages),
            "any_category": not window.categories,
            "categories": list(window.categories) or [""],
            "query_vector": _vector_literal(query_vector),
            "has_vector": query_vector is not None,
            "query_text": query_text,
            "limit": limit,
        },
    )
    hits = []
    for row in result.all():
        lexical_hit = row.rank is not None
        share = (row.rank / row.max_rank) if lexical_hit and row.max_rank else 0.0
        # No similarity when the model server is down or the window holds a
        # single article; full-text rank is then the only evidence.
        has_similarity = row.sim is not None and bool(row.std)
        z_score = (row.sim - row.mean) / row.std if has_similarity else 0.0
        if semantic and has_similarity:
            score = retrieval_score(z_score, lexical_hit)
        else:
            score = lexical_score(share, z_score, lexical_hit)
        hits.append(
            Hit(
                article_id=row.id,
                similarity=float(row.sim or 0.0),
                z_score=float(z_score),
                lexical_hit=lexical_hit,
                score=float(score),
            )
        )
    return hits


async def retrieve_candidates(
    session: AsyncSession,
    *,
    model: str,
    profile: ProfileSpec,
    window: Window,
    interest_vectors: dict[str, list[float]] | None,
    exclusion_vectors: dict[str, list[float]] | None,
    per_interest_limit: int,
    semantic: bool = True,
) -> tuple[list[Candidate], int]:
    """Collect candidates for every interest and mark the excluded ones.

    Returns the candidates (one per article and interest pair) and the number
    of articles published in the window.
    """
    by_interest: list[tuple[str, Hit]] = []
    for interest in profile.interests:
        hits = await search(
            session,
            model=model,
            window=window,
            query_vector=interest_vectors.get(interest.id) if interest_vectors else None,
            query_text=keyword_query(interest.keywords or (interest.title,)),
            limit=per_interest_limit,
            semantic=semantic,
        )
        by_interest.extend((interest.id, hit) for hit in hits)

    excluded: dict[int, tuple[str, float]] = {}
    for exclusion in profile.exclusions:
        hits = await search(
            session,
            model=model,
            window=window,
            query_vector=exclusion_vectors.get(exclusion) if exclusion_vectors else None,
            query_text=keyword_query((exclusion,)),
            limit=per_interest_limit,
            semantic=semantic,
        )
        for hit in hits:
            if (
                hit.score >= EXCLUSION_MIN_SCORE
                and hit.score > excluded.get(hit.article_id, ("", 0.0))[1]
            ):
                excluded[hit.article_id] = (exclusion, hit.score)

    refs = await get_refs(session, list({hit.article_id for _, hit in by_interest}))
    candidates = []
    for interest_id, hit in by_interest:
        article = refs.get(hit.article_id)
        if article is None:
            continue
        matched_exclusion = excluded.get(hit.article_id)
        candidates.append(
            Candidate(
                article=article,
                interest_id=interest_id,
                similarity=hit.similarity,
                z_score=hit.z_score,
                lexical_hit=hit.lexical_hit,
                retrieval_score=hit.score,
                excluded_by=_excluded_by(matched_exclusion, hit.score),
            )
        )
    total = await session.scalar(
        text(
            """
            SELECT count(*) FROM articles a JOIN sources s ON s.id = a.source_id
            WHERE a.published_at >= :start AND a.published_at < :end
              AND a.language = ANY(:languages)
              AND (:any_category OR s.category = ANY(:categories))
            """
        ),
        {
            "start": window.start,
            "end": window.end,
            "languages": list(window.languages),
            "any_category": not window.categories,
            "categories": list(window.categories) or [""],
        },
    )
    return candidates, int(total or 0)
