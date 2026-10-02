"""What the digest graph needs from the outside world."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

import numpy as np

from radar.ai.embedder import Embedder
from radar.ai.intelligence import Intelligence
from radar.domain import (
    Candidate,
    DigestOverview,
    GradedCandidate,
    ProfileSpec,
    Topic,
    VulnerabilityReference,
)
from radar.recsys.model import Learned, Personal
from radar.selection.retrieval import Window


class PipelineStore(Protocol):
    async def vulnerability_facts(self, ids: Sequence[str]) -> list[VulnerabilityReference]:
        """What CISA KEV and the BDU say of these CVE and BDU ids."""
        ...

    async def ensure_embeddings(self, start: datetime, end: datetime) -> int:
        """Embed articles of the period that lack a vector for the active model."""
        ...

    async def retrieve(
        self,
        profile: ProfileSpec,
        window: Window,
        interest_vectors: dict[str, list[float]] | None,
        exclusion_vectors: dict[str, list[float]] | None,
    ) -> tuple[list[Candidate], int]: ...

    async def vectors(self, article_ids: Sequence[int]) -> dict[int, np.ndarray]: ...

    async def personal(
        self, user_id: str, article_ids: Sequence[int], start: datetime, end: datetime
    ) -> dict[int, Personal]:
        """How the reader's likes and rejections move each candidate."""
        ...

    async def learned(
        self, user_id: str, profile_id: str, profile: ProfileSpec
    ) -> dict[str, Learned]:
        """What the profile's interests learned from the reader, when it follows them."""
        ...

    async def save(
        self,
        digest_id: str,
        *,
        overview: DigestOverview,
        topics: Sequence[Topic],
        graded: Sequence[GradedCandidate],
        rejected: dict[int, str],
        stats: dict[str, Any],
    ) -> None: ...


class QueryEmbedder(Protocol):
    async def __call__(self, texts: Sequence[str]) -> list[list[float]]: ...


@dataclass(frozen=True, slots=True)
class PipelineDeps:
    store: PipelineStore
    embedder: Embedder
    embed_queries: QueryEmbedder
    intelligence: Intelligence
    candidate_limit: int = 60
    llm_provider: str = "heuristic"
