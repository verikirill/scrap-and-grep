"""PostgreSQL implementation of the pipeline's storage port."""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

import numpy as np

from radar.ai.embedder import Embedder
from radar.cache import Cache
from radar.db import session_scope
from radar.domain import (
    Candidate,
    DigestOverview,
    GradedCandidate,
    ProfileSpec,
    Topic,
    VulnerabilityReference,
)
from radar.ingest.service import embed_pending
from radar.recsys.model import Learned, Personal
from radar.selection.retrieval import Window, retrieve_candidates
from radar.store import articles as article_store
from radar.store import digests as digest_store
from radar.text import stable_hash
from radar.vulns.lookup import lookup as vulnerability_lookup

QUERY_VECTOR_TTL = 7 * 24 * 3600


class SqlPipelineStore:
    def __init__(self, embedder: Embedder, per_interest_limit: int) -> None:
        self._embedder = embedder
        self._per_interest_limit = per_interest_limit

    async def ensure_embeddings(self, start: datetime, end: datetime) -> int:
        return await embed_pending(self._embedder, since=start, until=end)

    async def retrieve(
        self,
        profile: ProfileSpec,
        window: Window,
        interest_vectors: dict[str, list[float]] | None,
        exclusion_vectors: dict[str, list[float]] | None,
    ) -> tuple[list[Candidate], int]:
        async with session_scope() as session:
            return await retrieve_candidates(
                session,
                model=self._embedder.model_id,
                profile=profile,
                window=window,
                interest_vectors=interest_vectors,
                exclusion_vectors=exclusion_vectors,
                per_interest_limit=self._per_interest_limit,
                semantic=self._embedder.semantic,
            )

    async def vulnerability_facts(self, ids: Sequence[str]) -> list[VulnerabilityReference]:
        async with session_scope() as session:
            return await vulnerability_lookup(session, ids)

    async def vectors(self, article_ids: Sequence[int]) -> dict[int, np.ndarray]:
        async with session_scope() as session:
            return await article_store.load_vectors(session, self._embedder.model_id, article_ids)

    async def personal(
        self, user_id: str, article_ids: Sequence[int], start: datetime, end: datetime
    ) -> dict[int, Personal]:
        # Imported here: the recommender itself uses this module's query embedder.
        from radar.recsys.service import personal_adjustments

        return await personal_adjustments(uuid.UUID(user_id), article_ids, start, end)

    async def learned(
        self, user_id: str, profile_id: str, profile: ProfileSpec
    ) -> dict[str, Learned]:
        # Imported here like the recommender above.
        from radar.recsys.adaptation import learned_for

        async with session_scope() as session:
            return await learned_for(
                session,
                uuid.UUID(user_id),
                uuid.UUID(profile_id),
                profile,
                self._embedder.model_id,
            )

    async def save(
        self,
        digest_id: str,
        *,
        overview: DigestOverview,
        topics: Sequence[Topic],
        graded: Sequence[GradedCandidate],
        rejected: dict[int, str],
        stats: dict[str, Any],
    ) -> None:
        async with session_scope() as session:
            await digest_store.save_result(
                session,
                uuid.UUID(digest_id),
                overview=overview,
                topics=topics,
                graded=graded,
                rejected=rejected,
                stats=stats,
            )


class CachedQueryEmbedder:
    """Embed interest texts, remembering vectors between runs.

    A profile is embedded on every preview keystroke and every digest; its
    text rarely changes, so the vectors are worth keeping.
    """

    def __init__(self, embedder: Embedder, cache: Cache) -> None:
        self._embedder = embedder
        self._cache = cache

    async def __call__(self, texts: Sequence[str]) -> list[list[float]]:
        keys = [f"qvec:{stable_hash(self._embedder.model_id, text)}" for text in texts]
        found: dict[int, list[float]] = {}
        for index, key in enumerate(keys):
            hit = await self._cache.get_json(key)
            if hit is not None:
                found[index] = hit
        missing = [index for index in range(len(texts)) if index not in found]
        if missing:
            vectors = await self._embedder.embed([texts[index] for index in missing], "query")
            for index, vector in zip(missing, vectors, strict=True):
                found[index] = vector
                await self._cache.set_json(keys[index], vector, QUERY_VECTOR_TTL)
        return [found[index] for index in range(len(texts))]
