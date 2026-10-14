"""The digest graph end to end, with storage and models replaced by fakes."""

import asyncio
from collections.abc import Sequence
from datetime import date, datetime
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
    VulnerabilityReference,
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

    async def attack_techniques(self, ids: Sequence[str]) -> dict[str, str]:
        known = {"T1566": "Phishing"}
        return {value: known[value] for value in ids if value in known}

    async def vulnerability_facts(self, ids: Sequence[str]) -> list[VulnerabilityReference]:
        # One CVE in the CISA catalogue; the rest unknown.
        return [
            VulnerabilityReference(id=value, kev_added=date(2026, 9, 27))
            if value == "CVE-2026-2222"
            else VulnerabilityReference(id=value)
            for value in ids
        ]

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


@pytest.fixture
def security_week(make_article: ArticleFactory) -> list[ArticleRef]:
    return [
        make_article(
            "Атака группировки на SCADA ритейлера в Европе", "Хакеры зашифровали серверы."
        ),
        make_article(
            "Атака группировки на SCADA электросетей",
            "Пострадала российская электросетевая компания, вход был через подрядчика.",
        ),
        make_article(
            "Уязвимость SCADA-сервера CVE-2026-1111", "Эксплойт: существует в открытом доступе."
        ),
        make_article("Уязвимость в веб-интерфейсе SCADA", "Производитель выпустил патч."),
        make_article("Обзор рынка SCADA за год", "Аналитики оценили рынок АСУ ТП."),
    ]


async def test_a_specialist_digest_opens_with_attacks_and_vulnerabilities_by_priority(
    profile: ProfileSpec, security_week: list[ArticleRef]
) -> None:
    abroad, energy, exploited, patched, market = security_week
    store = FakeStore(security_week)
    graph = build_graph(_deps(store, HeuristicIntelligence())).compile(checkpointer=InMemorySaver())

    await graph.ainvoke(_input(profile.model_copy(update={"max_items": 10})), CONFIG)

    assert store.saved is not None
    topics: list[Topic] = store.saved["topics"]
    assert [topic.title for topic in topics[:2]] == ["Атаки", "Уязвимости"]
    # The dataset's rules: Russian energy above abroad, an exploit above a patch.
    assert [item.article.id for item in topics[0].items] == [energy.id, abroad.id]
    assert [item.article.id for item in topics[1].items] == [exploited.id, patched.id]
    assert market.id in {item.article.id for topic in topics[2:] for item in topic.items}
    assert store.saved["stats"]["priorities"] == {"high": 2, "medium": 1, "low": 1}


async def test_a_technique_the_article_prints_reaches_an_offline_card(
    profile: ProfileSpec, make_article: ArticleFactory
) -> None:
    article = make_article(
        "Атака группировки на SCADA электросетей",
        "Вход был через фишинговое письмо (T1566); сканер T1000 тут ни при чём.",
    )
    store = FakeStore([article])
    graph = build_graph(_deps(store, HeuristicIntelligence())).compile(checkpointer=InMemorySaver())

    await graph.ainvoke(_input(profile.model_copy(update={"max_items": 10})), CONFIG)

    assert store.saved is not None
    cards = [
        item.text.attack
        for topic in store.saved["topics"]
        for item in topic.items
        if item.text is not None and item.text.attack is not None
    ]
    assert [technique.id for card in cards for technique in card.techniques] == ["T1566"]


async def test_a_management_digest_has_topics_and_tags_instead_of_cards(
    profile: ProfileSpec, security_week: list[ArticleRef]
) -> None:
    store = FakeStore(security_week)
    graph = build_graph(_deps(store, HeuristicIntelligence())).compile(checkpointer=InMemorySaver())
    management = profile.model_copy(update={"max_items": 10, "audience": "management"})

    await graph.ainvoke(_input(management), CONFIG)

    assert store.saved is not None
    topics: list[Topic] = store.saved["topics"]
    assert not {"Атаки", "Уязвимости"} & {topic.title for topic in topics}
    entries = [item.text for topic in topics for item in topic.items]
    assert all(entry and entry.tags and entry.attack is None for entry in entries)


async def test_management_reads_no_identifiers_even_from_an_offline_digest(
    profile: ProfileSpec, security_week: list[ArticleRef]
) -> None:
    from radar.cards import technical_tokens
    from radar.text import split_sentences

    store = FakeStore(security_week)
    graph = build_graph(_deps(store, HeuristicIntelligence())).compile(checkpointer=InMemorySaver())
    management = profile.model_copy(update={"max_items": 10, "audience": "management"})

    await graph.ainvoke(_input(management), CONFIG)

    assert store.saved is not None
    entries = [item.text for topic in store.saved["topics"] for item in topic.items]
    assert entries
    for entry in entries:
        assert entry is not None
        assert technical_tokens(f"{entry.headline} {entry.summary} {entry.why}") == []
        assert len(split_sentences(entry.summary)) <= 2
    overview = store.saved["overview"]
    assert all(technical_tokens(line) == [] for line in overview.highlights)


async def test_a_vulnerability_the_text_is_quiet_about_is_raised_by_the_catalogue(
    profile: ProfileSpec, make_article: ArticleFactory
) -> None:
    # Nothing in the text says it is exploited; CISA KEV lists it.
    listed = make_article("Уязвимость CVE-2026-2222 в SCADA-сервере", "Вышло исправление.")
    other = make_article("Уязвимость CVE-2026-3333 в веб-интерфейсе SCADA", "Вышел патч.")
    store = FakeStore([listed, other])
    graph = build_graph(_deps(store, HeuristicIntelligence())).compile(checkpointer=InMemorySaver())

    await graph.ainvoke(_input(profile), CONFIG)

    assert store.saved is not None
    [section] = [topic for topic in store.saved["topics"] if topic.title == "Уязвимости"]
    first, second = section.items
    assert first.article.id == listed.id
    assert first.text.vulnerability.exploit == "in_the_wild"
    assert second.text.vulnerability.exploit == "unknown"
    assert store.saved["stats"]["lookups_by_pipeline"] == 2
    assert store.saved["stats"]["references_found"] == 1


async def test_a_card_keeps_only_the_references_about_its_own_vulnerability() -> None:
    from radar.domain import ItemSummary, VulnerabilityCard
    from radar.pipeline.graph import DigestNodes

    nodes = DigestNodes(_deps(FakeStore([]), HeuristicIntelligence()))
    card = ItemSummary(
        summary="",
        vulnerability=VulnerabilityCard(ids=("CVE-2026-92370", "BDU:2026-15497")),
        references=(
            # The model asked about a neighbour of the roundup, and about this CVE.
            VulnerabilityReference(id="CVE-2026-73570", kev_added=date(2026, 9, 20)),
            VulnerabilityReference(id="CVE-2026-92370", bdu_id="BDU:2026-15497", via="model"),
        ),
    )

    entry = await nodes._with_references(card, "CVE-2026-92370, BDU:2026-15497")

    # The BDU id is covered by the CVE's entry: nothing left to look up.
    assert [reference.id for reference in entry.references] == ["CVE-2026-92370"]


async def test_a_reference_from_the_answer_cache_is_looked_up_again() -> None:
    """An answer cached before the local copies of NVD, EPSS and Exploit-DB
    knew the CVE gets their facts; who asked first stays the model."""
    from radar.domain import ItemSummary, VulnerabilityCard
    from radar.pipeline.graph import DigestNodes

    class Richer(FakeStore):
        async def vulnerability_facts(self, ids: Sequence[str]) -> list[VulnerabilityReference]:
            return [
                VulnerabilityReference(
                    id=value, kev_added=date(2026, 9, 27), epss=0.42, exploits=("EDB-1",)
                )
                for value in ids
            ]

    nodes = DigestNodes(_deps(Richer([]), HeuristicIntelligence()))
    card = ItemSummary(
        summary="",
        vulnerability=VulnerabilityCard(ids=("CVE-2026-2222",)),
        references=(
            VulnerabilityReference(id="CVE-2026-2222", kev_added=date(2026, 9, 27), via="model"),
        ),
    )

    [reference] = (await nodes._with_references(card, "CVE-2026-2222")).references

    assert (reference.epss, reference.exploits, reference.via) == (0.42, ("EDB-1",), "model")


class TiedByBdu(FakeStore):
    """The bases know CVE-2026-104286 as BDU:2026-15790, as the BDU of FSTEC does."""

    async def vulnerability_facts(self, ids: Sequence[str]) -> list[VulnerabilityReference]:
        return [
            VulnerabilityReference(id=value, bdu_id="BDU:2026-15790", bdu_in_attacks=True)
            if value in ("CVE-2026-104286", "BDU:2026-15790")
            else VulnerabilityReference(id=value)
            for value in ids
        ]


async def test_two_entries_the_bases_tie_to_one_vulnerability_are_saved_as_one(
    profile: ProfileSpec, make_article: ArticleFactory
) -> None:
    """Selection merges by the ids an article prints; one post names the CVE,
    the other only its BDU entry, and the cards meet them."""
    english = make_article(
        "Уязвимость CVE-2026-104286 в SCADA-шлюзе FortiMail", "Обход пути и запись файлов."
    )
    russian = make_article(
        "Уязвимость BDU:2026-15790 в почтовом шлюзе", "Нарушитель записывает произвольные файлы."
    )
    store = TiedByBdu([english, russian])
    graph = build_graph(_deps(store, HeuristicIntelligence())).compile(checkpointer=InMemorySaver())

    await graph.ainvoke(_input(profile), CONFIG)

    assert store.saved is not None
    [section] = [topic for topic in store.saved["topics"] if topic.title == "Уязвимости"]
    [entry] = section.items
    assert entry.article.id == english.id
    assert [dup.url for dup in entry.duplicates] == [russian.url]
    assert store.saved["rejected"][russian.id] == "duplicate"
    assert store.saved["stats"]["duplicates_merged"] == 1


class AdvisesThePatch(HeuristicIntelligence):
    """A model answer like the one the jury read: the row knows the update is
    not out, the advice says to install it."""

    async def summarize(self, item: Any, profile: ProfileSpec, interest: Interest | None) -> Any:
        from radar.domain import ItemSummary, VulnerabilityCard

        return ItemSummary(
            headline=item.article.title,
            summary="Неавторизованный злоумышленник записывает произвольные файлы.",
            why="Срочно установите патч.",
            by_model=True,
            vulnerability=VulnerabilityCard(
                ids=("CVE-2026-104286",),
                fix="Обновить до FortiMail 7.4.9",
                workaround="Отключить IBE",
                exploit="in_the_wild",
            ),
        )


async def test_advice_to_patch_gives_way_to_the_workaround_when_the_fix_is_not_out(
    profile: ProfileSpec, make_article: ArticleFactory
) -> None:
    article = make_article(
        "Уязвимость CVE-2026-104286 в SCADA-шлюзе FortiMail",
        "Обновления пока недоступны, Fortinet называет версию 7.4.9. Пока их нет, отключите IBE.",
    )
    store = FakeStore([article])
    graph = build_graph(_deps(store, AdvisesThePatch())).compile(checkpointer=InMemorySaver())

    await graph.ainvoke(_input(profile), CONFIG)

    assert store.saved is not None
    [entry] = [item for topic in store.saved["topics"] for item in topic.items]
    assert entry.text.why == "Исправление ещё не выпущено, до его выхода: отключить IBE."
    assert (
        entry.text.vulnerability.fix == "Обновить до FortiMail 7.4.9. Исправление ещё не выпущено."
    )


class ModelGrades(CountingIntelligence):
    """A model's grades, as the cache keeps them: by_model is set."""

    async def grade(self, candidate: Candidate, profile: ProfileSpec) -> Grade:
        grade = await super().grade(candidate, profile)
        return grade.model_copy(update={"by_model": True})


async def test_the_second_audience_takes_its_grades_from_the_first(
    profile: ProfileSpec, security_week: list[ArticleRef]
) -> None:
    from radar.ai.resilient import CachedIntelligence
    from tests.test_resilience import MemoryCache

    model = ModelGrades()
    cached = CachedIntelligence(model, MemoryCache())  # type: ignore[arg-type]
    specialist = profile.model_copy(update={"max_items": 10})
    management = specialist.model_copy(update={"audience": "management"})
    stores = []
    for audience, spec in (("specialist", specialist), ("management", management)):
        store = FakeStore(security_week)
        graph = build_graph(_deps(store, cached)).compile(checkpointer=InMemorySaver())
        await graph.ainvoke(_input(spec), {"configurable": {"thread_id": audience}})
        stores.append(store)
        if audience == "specialist":
            graded_once, written_once = model.grade_calls, model.summary_calls

    # One grading for both: the audience changes how an entry is written, not its grade.
    assert graded_once > 0
    assert model.grade_calls == graded_once
    assert model.summary_calls > written_once
    first, second = (store.saved for store in stores)
    assert first is not None
    assert second is not None
    assert [topic.title for topic in first["topics"][:2]] == ["Атаки", "Уязвимости"]
    assert not {"Атаки", "Уязвимости"} & {topic.title for topic in second["topics"]}
