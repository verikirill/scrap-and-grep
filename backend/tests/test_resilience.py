"""Circuit breaker and answer cache around the model server."""

from typing import Any

from radar.ai.heuristic import HeuristicIntelligence
from radar.ai.resilient import CachedIntelligence, CircuitBreaker, ResilientIntelligence
from radar.domain import Candidate, Grade, ProfileSpec
from tests.conftest import ArticleFactory


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class FlakyModel(HeuristicIntelligence):
    name = "ollama:test"

    def __init__(self) -> None:
        self.calls = 0
        self.healthy = False

    async def grade(self, candidate: Candidate, profile: ProfileSpec) -> Grade:
        self.calls += 1
        if not self.healthy:
            raise ConnectionError("refused")
        return Grade(relevance=3, interest_id=candidate.interest_id, reason="model", by_model=True)


class MemoryCache:
    def __init__(self) -> None:
        self.data: dict[str, Any] = {}

    async def get_json(self, key: str) -> Any | None:
        return self.data.get(key)

    async def set_json(self, key: str, value: Any, ttl: int) -> None:
        self.data[key] = value


def test_breaker_opens_after_consecutive_failures_and_allows_a_trial_later() -> None:
    clock = Clock()
    breaker = CircuitBreaker(failure_threshold=2, reset_seconds=30, clock=clock)

    breaker.record_failure()
    assert breaker.allow()
    breaker.record_failure()
    assert not breaker.allow()

    clock.now = 31
    assert breaker.allow()
    breaker.record_success()
    breaker.record_failure()
    assert breaker.allow()


async def test_open_breaker_stops_calling_the_model_until_it_recovers(
    profile: ProfileSpec, make_article: ArticleFactory
) -> None:
    clock = Clock()
    model = FlakyModel()
    resilient = ResilientIntelligence(
        model, HeuristicIntelligence(), CircuitBreaker(2, reset_seconds=30, clock=clock)
    )
    candidate = Candidate(article=make_article("SCADA"), interest_id="ics", retrieval_score=0.8)

    grades = [await resilient.grade(candidate, profile) for _ in range(5)]

    assert model.calls == 2
    assert all(not grade.by_model for grade in grades)

    model.healthy = True
    clock.now = 31
    recovered = await resilient.grade(candidate, profile)

    assert recovered.by_model
    assert model.calls == 3


async def test_cache_stores_model_answers_but_never_fallback_answers(
    profile: ProfileSpec, make_article: ArticleFactory
) -> None:
    model = FlakyModel()
    cache = MemoryCache()
    cached = CachedIntelligence(
        ResilientIntelligence(model, HeuristicIntelligence(), CircuitBreaker(100)),
        cache,  # type: ignore[arg-type]
    )
    candidate = Candidate(article=make_article("SCADA"), interest_id="ics", retrieval_score=0.8)

    await cached.grade(candidate, profile)
    assert cache.data == {}

    model.healthy = True
    first = await cached.grade(candidate, profile)
    second = await cached.grade(candidate, profile)

    assert first.by_model
    assert second == first
    assert model.calls == 2
