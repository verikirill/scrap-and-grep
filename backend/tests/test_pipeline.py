"""The digest graph end to end, with storage and models replaced by fakes."""

import asyncio
from collections.abc import Sequence
from datetime import datetime
from typing import Any

import numpy as np
import pytest
from langgraph.checkpoint.memory import InMemorySaver

from radar.ai.embedder import HashingEmbedder
from radar.ai.heuristic import HeuristicIntelligence
from radar.ai.resilient import CircuitBreaker, ResilientIntelligence
from radar.domain import (
    ArticleRef,
    Candidate,
    DigestOverview,
    Grade,
    GradedCandidate,
    Interest,
    ProfileSpec,
    Topic,
)
from radar.pipeline.graph import DigestState, build_graph
from radar.pipeline.ports import PipelineDeps
from radar.recsys.model import Learned, Personal
from radar.selection.retrieval import Window
from radar.text import tokenize
from tests.conftest import ArticleFactory

CONFIG: Any = {"configurable": {"thread_id": "digest-1"}}


class FakeStore:
    """Keyword retrieval over an in-memory list; records what gets saved."""

    def __init__(
        self,
        articles: list[ArticleRef],
        fail_saves: int = 0,
        learned: dict[str, Learned] | None = None,
    ) -> None:
        self.articles = articles
        self.saved: dict[str, Any] | None = None
        self._fail_saves = fail_saves
        self._learned = learned or {}

    async def ensure_embeddings(self, start: datetime, end: datetime) -> int:
        return 0

    async def retrieve(
        self,
        profile: ProfileSpec,
        window: Window,
        interest_vectors: dict[str, list[float]] | None,
        exclusion_vectors: dict[str, list[float]] | None,
    ) -> tuple[list[Candidate], int]:
        candidates = []
        for interest in profile.interests:
            keywords = {token for keyword in interest.keywords for token in tokenize(keyword)}
            for article in self.articles:
                hit = bool(keywords & set(tokenize(f"{article.title} {article.summary}")))
                excluded = next(
                    (item for item in profile.exclusions if item.lower() in article.title.lower()),
                    None,
                )
                candidates.append(
                    Candidate(
                        article=article,
                        interest_id=interest.id,
                        lexical_hit=hit,
                        retrieval_score=0.8 if hit else 0.2,
                        excluded_by=excluded,
                    )
                )
        return candidates, len(self.articles)

    async def vectors(self, article_ids: Sequence[int]) -> dict[int, np.ndarray]:
        return {}

    async def personal(
        self, user_id: str, article_ids: Sequence[int], start: datetime, end: datetime
    ) -> dict[int, Personal]:
        return {}

    async def learned(
        self, user_id: str, profile_id: str, profile: ProfileSpec
    ) -> dict[str, Learned]:
        return self._learned

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
        if self._fail_saves > 0:
            self._fail_saves -= 1
            raise ConnectionError("database went away")
        self.saved = {
            "overview": overview,
            "topics": list(topics),
            "graded": list(graded),
            "rejected": rejected,
            "stats": stats,
        }


class CountingIntelligence(HeuristicIntelligence):
    def __init__(self) -> None:
        self.grade_calls = 0
        self.summary_calls = 0

    async def grade(self, candidate: Candidate, profile: ProfileSpec) -> Grade:
        self.grade_calls += 1
        return await super().grade(candidate, profile)

    async def summarize(self, item: Any, profile: ProfileSpec, interest: Interest | None) -> Any:
        self.summary_calls += 1
        return await super().summarize(item, profile, interest)


class BrokenModel(HeuristicIntelligence):
    name = "ollama:broken"

    async def grade(self, candidate: Candidate, profile: ProfileSpec) -> Grade:
        raise TimeoutError("model server does not answer")

    async def summarize(self, item: Any, profile: ProfileSpec, interest: Interest | None) -> Any:
        raise TimeoutError("model server does not answer")

    async def name_topic(self, items: Any, profile: ProfileSpec) -> Any:
        raise TimeoutError("model server does not answer")

    async def overview(self, topics: Any, profile: ProfileSpec) -> Any:
        raise TimeoutError("model server does not answer")


async def _embed_queries(texts: Sequence[str]) -> list[list[float]]:
    return await HashingEmbedder().embed(list(texts), "query")


def _deps(store: FakeStore, intelligence: Any, llm_provider: str = "heuristic") -> PipelineDeps:
    return PipelineDeps(
        store=store,
        embedder=HashingEmbedder(),
        embed_queries=_embed_queries,
        intelligence=intelligence,
        llm_provider=llm_provider,
    )


def _input(profile: ProfileSpec) -> DigestState:
    return {
        "digest_id": "digest-1",
        "profile": profile.model_dump(mode="json"),
        "period_start": "2026-09-23T00:00:00+00:00",
        "period_end": "2026-09-30T00:00:00+00:00",
    }


@pytest.fixture
def articles(make_article: ArticleFactory) -> list[ArticleRef]:
    return [
        make_article("Уязвимость в SCADA-системе подстанции", "Производитель выпустил патч."),
        make_article("Новая CVE в ядре Linux", "Уязвимость позволяет повысить привилегии."),
        make_article("Вакансии: инженер SCADA", "Ищем специалиста."),
        make_article("Квартальная отчётность ритейлера", "Выручка выросла на 3%."),
    ]


async def test_digest_groups_relevant_articles_and_keeps_their_links(
    profile: ProfileSpec, articles: list[ArticleRef]
) -> None:
    store = FakeStore(articles)
    graph = build_graph(_deps(store, HeuristicIntelligence())).compile(checkpointer=InMemorySaver())

    await graph.ainvoke(_input(profile), CONFIG)

    assert store.saved is not None
    topics: list[Topic] = store.saved["topics"]
    in_digest = {item.article.url: topic.title for topic in topics for item in topic.items}
    assert set(in_digest) == {articles[0].url, articles[1].url}
    assert len({topic.title for topic in topics}) == len(topics) == 2
    assert store.saved["rejected"][articles[2].id] == "excluded"
    assert store.saved["rejected"][articles[3].id] == "low_score"
    assert all(item.text and item.text.summary for topic in topics for item in topic.items)
    assert store.saved["stats"]["selected"] == 2
    assert store.saved["stats"]["degraded"] is False


async def test_changing_interests_changes_the_selection(
    profile: ProfileSpec, articles: list[ArticleRef]
) -> None:
    finance = profile.model_copy(
        update={
            "interests": (Interest(id="fin", title="Финансы", keywords=("отчётность", "выручка")),),
            "exclusions": (),
        }
    )
    store = FakeStore(articles)
    graph = build_graph(_deps(store, HeuristicIntelligence())).compile(checkpointer=InMemorySaver())

    await graph.ainvoke(_input(finance), CONFIG)

    assert store.saved is not None
    selected = [item.article.id for topic in store.saved["topics"] for item in topic.items]
    assert selected == [articles[3].id]


async def test_failed_run_resumes_from_checkpoint_without_repeating_model_calls(
    profile: ProfileSpec, articles: list[ArticleRef]
) -> None:
    # The save fails through all three attempts of the node's retry policy.
    store = FakeStore(articles, fail_saves=3)
    intelligence = CountingIntelligence()
    graph = build_graph(_deps(store, intelligence)).compile(checkpointer=InMemorySaver())

    with pytest.raises(ConnectionError):
        await graph.ainvoke(_input(profile), CONFIG)
    calls_before_resume = (intelligence.grade_calls, intelligence.summary_calls)
    assert (await graph.aget_state(CONFIG)).next == ("persist",)

    await graph.ainvoke(None, CONFIG)

    assert store.saved is not None
    assert (intelligence.grade_calls, intelligence.summary_calls) == calls_before_resume
    assert store.saved["stats"]["selected"] == 2


async def test_failed_grade_is_the_only_one_repeated_on_resume(
    profile: ProfileSpec, articles: list[ArticleRef]
) -> None:
    class FailsOnce(CountingIntelligence):
        def __init__(self, article_id: int) -> None:
            super().__init__()
            self.graded: list[int] = []
            self._fail_for: int | None = article_id

        async def grade(self, candidate: Candidate, profile: ProfileSpec) -> Grade:
            self.graded.append(candidate.article.id)
            if candidate.article.id == self._fail_for:
                # Let the sibling tasks of the fan-out finish first.
                await asyncio.sleep(0.1)
                self._fail_for = None
                raise ConnectionError("model server dropped the connection")
            return await super().grade(candidate, profile)

    store = FakeStore(articles)
    intelligence = FailsOnce(articles[1].id)
    graph = build_graph(_deps(store, intelligence)).compile(checkpointer=InMemorySaver())

    with pytest.raises(ConnectionError):
        await graph.ainvoke(_input(profile), CONFIG)
    graded_in_first_attempt = len(intelligence.graded)

    await graph.ainvoke(None, CONFIG)

    assert intelligence.graded[graded_in_first_attempt:] == [articles[1].id]
    assert store.saved is not None
    assert store.saved["stats"]["candidates"] == len(articles)


async def test_model_outage_degrades_to_heuristic_instead_of_failing(
    profile: ProfileSpec, articles: list[ArticleRef]
) -> None:
    store = FakeStore(articles)
    resilient = ResilientIntelligence(
        BrokenModel(), HeuristicIntelligence(), CircuitBreaker(failure_threshold=2)
    )
    graph = build_graph(_deps(store, resilient, llm_provider="ollama")).compile(
        checkpointer=InMemorySaver()
    )

    await graph.ainvoke(_input(profile), CONFIG)

    assert store.saved is not None
    stats = store.saved["stats"]
    assert stats["selected"] == 2
    assert stats["degraded"] is True
    assert stats["graded_by_model"] == 0


async def test_empty_period_produces_an_empty_digest_not_an_error(profile: ProfileSpec) -> None:
    store = FakeStore([])
    graph = build_graph(_deps(store, HeuristicIntelligence())).compile(checkpointer=InMemorySaver())

    await graph.ainvoke(_input(profile), CONFIG)

    assert store.saved is not None
    assert store.saved["topics"] == []
    assert store.saved["stats"]["selected"] == 0


async def test_a_profile_that_learned_from_its_reader_weighs_its_interests_accordingly(
    profile: ProfileSpec, articles: list[ArticleRef]
) -> None:
    """Interests the reader's marks favour count for more, the others for less,
    and the digest records what it used."""
    learned = {"ics": Learned(factor=1.25, positives=6.0), "vuln": Learned(factor=0.75)}
    runs = {}
    for name, store in (
        ("stated", FakeStore(articles)),
        ("learned", FakeStore(articles, learned=learned)),
    ):
        graph = build_graph(_deps(store, HeuristicIntelligence())).compile(
            checkpointer=InMemorySaver()
        )
        state = {**_input(profile), "user_id": "user-1", "profile_id": "profile-1"}
        await graph.ainvoke(state, {"configurable": {"thread_id": name}})
        assert store.saved is not None
        runs[name] = store.saved

    def score(saved: dict[str, Any], article: ArticleRef) -> float:
        return next(item.score for item in saved["graded"] if item.article.id == article.id)

    # Only the "vulnerabilities" interest brings the Linux CVE: its score drops by a quarter.
    linux = articles[1]
    assert score(runs["learned"], linux) == pytest.approx(score(runs["stated"], linux) * 0.75)
    assert runs["learned"]["stats"]["adaptation"]["ics"]["factor"] == 1.25
    assert runs["stated"]["stats"]["adaptation"] == {}
