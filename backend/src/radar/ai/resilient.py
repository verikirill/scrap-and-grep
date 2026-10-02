"""Fault tolerance around the model server: circuit breaker, fallback, cache."""

import time
from collections.abc import Awaitable, Callable, Sequence

from radar.ai.intelligence import Intelligence
from radar.ai.prompts import PROMPT_VERSION, SUMMARY_PROMPT_VERSION
from radar.cache import Cache
from radar.domain import (
    Candidate,
    DigestOverview,
    Grade,
    Interest,
    ItemSummary,
    ProfileSpec,
    SelectedItem,
    Topic,
    TopicName,
)
from radar.logging import get_logger
from radar.text import stable_hash

log = get_logger(__name__)

GRADE_TTL = 7 * 24 * 3600
SUMMARY_TTL = 30 * 24 * 3600


class CircuitBreaker:
    """Stop calling a failing dependency for a while instead of queueing on it.

    Closed: calls pass. After `failure_threshold` consecutive failures the
    breaker opens and calls are refused until `reset_seconds` pass. Calls are
    then let through again; the first success closes it, the next failure
    re-opens it for another `reset_seconds`.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        reset_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._threshold = failure_threshold
        self._reset = reset_seconds
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        return self._opened_at is not None and self._clock() - self._opened_at < self._reset

    def allow(self) -> bool:
        return not self.is_open

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._threshold:
            self._opened_at = self._clock()


class ResilientIntelligence:
    """Try the primary provider, fall back to the offline one on any failure.

    A digest that is partly written by the heuristic is better than no digest.
    Results carry `by_model=False` when the fallback produced them, so the
    report can say how much of it was degraded.
    """

    def __init__(
        self, primary: Intelligence, fallback: Intelligence, breaker: CircuitBreaker
    ) -> None:
        self.name = primary.name
        self._primary = primary
        self._fallback = fallback
        self._breaker = breaker

    async def _call[T](
        self,
        operation: str,
        primary: Callable[[], Awaitable[T]],
        fallback: Callable[[], Awaitable[T]],
    ) -> T:
        if self._breaker.allow():
            try:
                result = await primary()
            except Exception as exc:
                self._breaker.record_failure()
                log.warning(
                    "llm_call_failed",
                    operation=operation,
                    provider=self._primary.name,
                    error=f"{type(exc).__name__}: {exc}"[:300],
                    breaker_open=self._breaker.is_open,
                )
            else:
                self._breaker.record_success()
                return result
        return await fallback()

    async def grade(self, candidate: Candidate, profile: ProfileSpec) -> Grade:
        return await self._call(
            "grade",
            lambda: self._primary.grade(candidate, profile),
            lambda: self._fallback.grade(candidate, profile),
        )

    async def summarize(
        self, item: SelectedItem, profile: ProfileSpec, interest: Interest | None
    ) -> ItemSummary:
        return await self._call(
            "summarize",
            lambda: self._primary.summarize(item, profile, interest),
            lambda: self._fallback.summarize(item, profile, interest),
        )

    async def name_topic(self, items: Sequence[SelectedItem], profile: ProfileSpec) -> TopicName:
        return await self._call(
            "name_topic",
            lambda: self._primary.name_topic(items, profile),
            lambda: self._fallback.name_topic(items, profile),
        )

    async def overview(self, topics: Sequence[Topic], profile: ProfileSpec) -> DigestOverview:
        return await self._call(
            "overview",
            lambda: self._primary.overview(topics, profile),
            lambda: self._fallback.overview(topics, profile),
        )


class CachedIntelligence:
    """Remember per-article model answers.

    Grading and summarising dominate the cost of a digest, and the same
    article is judged again every time a digest is rebuilt for an unchanged
    profile. Only model answers are stored: a fallback answer must not mask
    the model once it is back.
    """

    def __init__(self, inner: Intelligence, cache: Cache) -> None:
        self.name = inner.name
        self._inner = inner
        self._cache = cache

    async def grade(self, candidate: Candidate, profile: ProfileSpec) -> Grade:
        key = "grade:" + stable_hash(
            self.name, PROMPT_VERSION, profile.fingerprint(), candidate.article.content_hash
        )
        hit = await self._cache.get_json(key)
        if hit is not None:
            return Grade.model_validate(hit)
        grade = await self._inner.grade(candidate, profile)
        if grade.by_model:
            await self._cache.set_json(key, grade.model_dump(), GRADE_TTL)
        return grade

    async def summarize(
        self, item: SelectedItem, profile: ProfileSpec, interest: Interest | None
    ) -> ItemSummary:
        key = "summary:" + stable_hash(
            self.name,
            SUMMARY_PROMPT_VERSION,
            profile.role,
            interest.model_dump_json() if interest else "",
            item.article.content_hash,
        )
        hit = await self._cache.get_json(key)
        if hit is not None:
            return ItemSummary.model_validate(hit)
        summary = await self._inner.summarize(item, profile, interest)
        if summary.by_model:
            await self._cache.set_json(key, summary.model_dump(), SUMMARY_TTL)
        return summary

    async def name_topic(self, items: Sequence[SelectedItem], profile: ProfileSpec) -> TopicName:
        return await self._inner.name_topic(items, profile)

    async def overview(self, topics: Sequence[Topic], profile: ProfileSpec) -> DigestOverview:
        return await self._inner.overview(topics, profile)
