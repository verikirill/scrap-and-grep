"""The digest pipeline as a LangGraph state graph.

    prepare -> retrieve -> grade (one task per candidate) -> select -> cluster
            -> summarize (per item) + name_topic (per topic) -> compose -> persist

A specialist's digest opens with two fixed sections, attacks and
vulnerabilities, each in the priority order of the organizers' dataset; the
rest of the news is clustered into topics. Management gets topics only.

State holds JSON-ready dicts only. With a Postgres checkpointer every finished
step survives a worker crash, and a redelivered task resumes from the step
that was interrupted.

Inside a fan-out step the guarantee depends on how the attempt ended. If one
task fails, the results of its siblings are kept and only the failed task runs
again. If the process is killed, the whole step restarts: LangGraph writes the
results of a step's tasks when the step ends (measured with both "async" and
"sync" durability). The model calls are still not paid for twice, because each
answer is cached the moment it arrives (ai/resilient.py).
"""

import operator
import time
from datetime import datetime
from typing import Annotated, Any, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy, Send

from radar.cards import (
    PRIORITY_ORDER,
    SECTION_KINDS,
    SECTION_TITLES,
    check_entry,
    priority,
    section_overview,
    source_text,
)
from radar.domain import (
    Candidate,
    DigestOverview,
    Grade,
    GradedCandidate,
    ItemSummary,
    ProfileSpec,
    RecordKind,
    SelectedItem,
    Topic,
    TopicName,
)
from radar.logging import get_logger
from radar.pipeline.ports import PipelineDeps
from radar.recsys.model import Learned, adapted_weight
from radar.selection.clustering import cluster_items
from radar.selection.retrieval import Window
from radar.selection.scoring import final_score, rank_candidates, select

log = get_logger(__name__)

# Enough for the summary prompt; keeps checkpoints small.
STATE_CONTENT_LIMIT = 4000
# Backstop only. A slow model call times out on its own (llm_timeout_seconds)
# and falls back to the heuristic; this bounds a node that hangs elsewhere.
MODEL_NODE_TIMEOUT = 900.0
_IO_RETRY = RetryPolicy(max_attempts=3, initial_interval=1.0, backoff_factor=2.0)
# Marks candidates the reader's behaviour could not be applied to.
_UNPERSONALIZED = "без учёта оценок: сбой при расчёте"


class DigestState(TypedDict, total=False):
    digest_id: str
    user_id: str
    # The profile the digest was ordered for; None for one deleted since.
    profile_id: str | None
    profile: dict[str, Any]
    # What the profile's interests learned from the reader, as used here:
    # interest id -> factor, drift and the marks behind them.
    adaptation: dict[str, dict[str, float]]
    period_start: str
    period_end: str
    started_at: float
    embedded_now: int
    lexical_only: bool
    window_total: int
    candidates: list[dict[str, Any]]
    graded: Annotated[list[dict[str, Any]], operator.add]
    personalized: list[dict[str, Any]]
    selected: list[dict[str, Any]]
    rejected: dict[str, str]
    groups: list[list[int]]
    # The record kind of a fixed section, None for a topic the model names.
    group_kinds: list[str | None]
    summaries: Annotated[list[dict[str, Any]], operator.add]
    topic_names: Annotated[list[dict[str, Any]], operator.add]
    overview: dict[str, Any]
    topics: list[dict[str, Any]]


class GradeTask(TypedDict, total=False):
    candidate: dict[str, Any]
    profile: dict[str, Any]
    adaptation: dict[str, dict[str, float]]


class SummaryTask(TypedDict):
    item: dict[str, Any]
    profile: dict[str, Any]


class TopicTask(TypedDict):
    index: int
    items: list[dict[str, Any]]
    profile: dict[str, Any]


def _emit(stage: str, **fields: Any) -> None:
    get_stream_writer()({"stage": stage, **fields})


def _profile(state: DigestState) -> ProfileSpec:
    return ProfileSpec.model_validate(state["profile"])


class DigestNodes:
    """Graph nodes. Each returns the state update it is responsible for."""

    def __init__(self, deps: PipelineDeps) -> None:
        self._deps = deps

    async def prepare(self, state: DigestState) -> dict[str, Any]:
        _emit("prepare")
        start = datetime.fromisoformat(state["period_start"])
        end = datetime.fromisoformat(state["period_end"])
        try:
            embedded = await self._deps.store.ensure_embeddings(start, end)
        except Exception as exc:
            # The embedding server is down. Articles embedded earlier are still
            # searchable, the rest are reachable through full-text search.
            log.warning("ensure_embeddings_failed", error=f"{type(exc).__name__}: {exc}"[:300])
            embedded = 0
        return {"embedded_now": embedded, "started_at": time.time()}

    async def retrieve(self, state: DigestState) -> dict[str, Any]:
        _emit("retrieve")
        profile = _profile(state)
        window = Window(
            start=datetime.fromisoformat(state["period_start"]),
            end=datetime.fromisoformat(state["period_end"]),
            languages=profile.languages,
            categories=profile.categories,
        )
        interest_vectors: dict[str, list[float]] | None
        exclusion_vectors: dict[str, list[float]] | None
        try:
            texts = [interest.as_query() for interest in profile.interests]
            vectors = await self._deps.embed_queries([*texts, *profile.exclusions])
            interest_vectors = {
                interest.id: vector
                for interest, vector in zip(profile.interests, vectors, strict=False)
            }
            exclusion_vectors = dict(
                zip(profile.exclusions, vectors[len(profile.interests) :], strict=True)
            )
            lexical_only = False
        except Exception as exc:
            log.warning("query_embedding_failed", error=f"{type(exc).__name__}: {exc}"[:300])
            interest_vectors, exclusion_vectors, lexical_only = None, None, True

        learned = await self._learned(state, profile)
        if interest_vectors is not None:
            # Interests that learned where the reader's liked articles are search there.
            interest_vectors = {
                interest_id: learned[interest_id].vector or vector
                if interest_id in learned
                else vector
                for interest_id, vector in interest_vectors.items()
            }

        candidates, total = await self._deps.store.retrieve(
            profile, window, interest_vectors, exclusion_vectors
        )
        ranked = rank_candidates(candidates, self._deps.candidate_limit)
        trimmed = [
            candidate.model_copy(
                update={
                    "article": candidate.article.model_copy(
                        update={"content": candidate.article.body(STATE_CONTENT_LIMIT) or None}
                    )
                }
            )
            for candidate in ranked
        ]
        _emit("grade", total=len(trimmed), done=0)
        return {
            "candidates": [candidate.model_dump(mode="json") for candidate in trimmed],
            "window_total": total,
            "lexical_only": lexical_only,
            "adaptation": {
                interest_id: {
                    "factor": item.factor,
                    "drift": item.drift,
                    "positives": item.positives,
                    "negatives": item.negatives,
                    "skipped": float(item.skipped),
                }
                for interest_id, item in learned.items()
            },
        }

    async def _learned(self, state: DigestState, profile: ProfileSpec) -> dict[str, Learned]:
        """What the profile learned from its reader. Best effort, like _personalize:
        without it the digest follows the stated interests."""
        user_id, profile_id = state.get("user_id"), state.get("profile_id")
        if not user_id or not profile_id:
            return {}
        try:
            return await self._deps.store.learned(user_id, profile_id, profile)
        except Exception as exc:
            log.warning("adaptation_unavailable", error=f"{type(exc).__name__}: {exc}"[:300])
            return {}

    def fan_out_grading(self, state: DigestState) -> list[Send] | str:
        if not state["candidates"]:
            return "select"
        return [
            Send(
                "grade",
                {
                    "candidate": candidate,
                    "profile": state["profile"],
                    "adaptation": state.get("adaptation", {}),
                },
            )
            for candidate in state["candidates"]
        ]

    async def grade(self, state: GradeTask) -> dict[str, Any]:
        candidate = Candidate.model_validate(state["candidate"])
        profile = ProfileSpec.model_validate(state["profile"])
        if candidate.excluded_by is not None:
            verdict = Grade(
                relevance=0,
                interest_id=candidate.interest_id,
                reason=f"Попадает под исключение «{candidate.excluded_by}».",
            )
        else:
            verdict = await self._deps.intelligence.grade(candidate, profile)
        interest = profile.interest(verdict.interest_id or candidate.interest_id)
        weight = 1.0
        if interest is not None:
            own = state.get("adaptation", {}).get(interest.id)
            weight = adapted_weight(interest.weight, Learned(factor=own["factor"]) if own else None)
        graded = GradedCandidate(
            candidate=candidate,
            grade=verdict,
            score=final_score(candidate, verdict, weight),
        )
        _emit("grade", done=1)
        return {"graded": [graded.model_dump(mode="json")]}

    async def select_items(self, state: DigestState) -> dict[str, Any]:
        _emit("select")
        profile = _profile(state)
        graded = [GradedCandidate.model_validate(item) for item in state.get("graded", [])]
        graded = await self._personalize(state, graded)
        vectors = await self._deps.store.vectors([item.article.id for item in graded])
        selected, rejected = select(
            graded, profile, vectors, self._deps.embedder.duplicate_threshold
        )
        return {
            # Replaces the list the grading tasks accumulated: from here on
            # every candidate carries its personal adjustment.
            "personalized": [item.model_dump(mode="json") for item in graded],
            "selected": [item.model_dump(mode="json") for item in selected],
            "rejected": {str(article_id): reason for article_id, reason in rejected.items()},
        }

    async def _personalize(
        self, state: DigestState, graded: list[GradedCandidate]
    ) -> list[GradedCandidate]:
        """Let the reader's likes and rejections move the scores.

        Best effort: a digest built on stated interests alone is still a
        digest, so a failure here is logged and skipped.
        """
        user_id = state.get("user_id")
        if not user_id or not graded:
            return graded
        try:
            personal = await self._deps.store.personal(
                user_id,
                [item.article.id for item in graded],
                datetime.fromisoformat(state["period_start"]),
                datetime.fromisoformat(state["period_end"]),
            )
        except Exception as exc:
            log.warning("personalization_failed", error=f"{type(exc).__name__}: {exc}"[:300])
            # Recorded in the stats: the reader's hidden articles may be back.
            return [item.model_copy(update={"personal_note": _UNPERSONALIZED}) for item in graded]
        adjusted = []
        for item in graded:
            change = personal.get(item.article.id)
            if change is None:
                adjusted.append(item)
                continue
            adjusted.append(
                item.model_copy(
                    update={
                        "score": float(min(1.0, max(0.0, item.score + change.delta))),
                        "personal": change.delta,
                        "personal_note": change.note,
                        "rejected_by_reader": change.rejected,
                    }
                )
            )
        return adjusted

    async def cluster(self, state: DigestState) -> dict[str, Any]:
        profile = _profile(state)
        selected = [SelectedItem.model_validate(item) for item in state["selected"]]
        sections: list[list[SelectedItem]] = []
        kinds: list[str | None] = []
        rest = selected
        if profile.audience == "specialist":
            for kind in SECTION_TITLES:
                members = [item for item in selected if item.graded.grade.kind == kind]
                if members:
                    sections.append(members)
                    kinds.append(kind)
            rest = [item for item in selected if item.graded.grade.kind not in SECTION_TITLES]
        groups: list[list[SelectedItem]] = []
        if rest:
            vectors = await self._deps.store.vectors([item.article.id for item in rest])
            groups = cluster_items(rest, vectors, semantic=self._deps.embedder.semantic)
        _emit("summarize", total=len(selected), done=0)
        return {
            "groups": [[item.article.id for item in group] for group in [*sections, *groups]],
            "group_kinds": [*kinds, *[None] * len(groups)],
        }

    def fan_out_writing(self, state: DigestState) -> list[Send] | str:
        if not state["selected"]:
            return "compose"
        by_id = {item["graded"]["candidate"]["article"]["id"]: item for item in state["selected"]}
        tasks = [
            Send("summarize", {"item": item, "profile": state["profile"]})
            for item in state["selected"]
        ]
        kinds = state.get("group_kinds") or [None] * len(state["groups"])
        tasks += [
            Send(
                "name_topic",
                {
                    "index": index,
                    "items": [by_id[article_id] for article_id in group],
                    "profile": state["profile"],
                },
            )
            for index, group in enumerate(state["groups"])
            # A fixed section has its name already.
            if kinds[index] is None
        ]
        return tasks

    async def summarize(self, state: SummaryTask) -> dict[str, Any]:
        item = SelectedItem.model_validate(state["item"])
        profile = ProfileSpec.model_validate(state["profile"])
        interest = profile.interest(item.graded.interest_id)
        written = await self._deps.intelligence.summarize(item, profile, interest)
        # Checked here, past the answer cache: a better check applies to answers
        # cached before it without paying for them again.
        article = item.article
        text = check_entry(written, source_text(article.title, article.summary, article.content))
        _emit("summarize", done=1)
        return {"summaries": [{"article_id": item.article.id, "text": text.model_dump()}]}

    async def name_topic(self, state: TopicTask) -> dict[str, Any]:
        items = [SelectedItem.model_validate(item) for item in state["items"]]
        profile = ProfileSpec.model_validate(state["profile"])
        name = await self._deps.intelligence.name_topic(items, profile)
        return {"topic_names": [{"index": state["index"], "name": name.model_dump()}]}

    async def compose(self, state: DigestState) -> dict[str, Any]:
        _emit("compose")
        profile = _profile(state)
        texts = {
            entry["article_id"]: ItemSummary.model_validate(entry["text"])
            for entry in state.get("summaries", [])
        }
        names = {
            entry["index"]: TopicName.model_validate(entry["name"])
            for entry in state.get("topic_names", [])
        }
        items = {
            item.article.id: item.model_copy(update={"text": texts.get(item.article.id)})
            for item in (SelectedItem.model_validate(raw) for raw in state["selected"])
        }
        groups = state.get("groups", [])
        kinds = state.get("group_kinds") or [None] * len(groups)
        topics = _unique_titles(
            [
                _section(SECTION_KINDS[kind], [items[article_id] for article_id in group])
                if kind in SECTION_KINDS
                else Topic(
                    title=names[index].title if index in names else "Разное",
                    overview=names[index].overview if index in names else "",
                    items=tuple(items[article_id] for article_id in group),
                )
                for index, (group, kind) in enumerate(zip(groups, kinds, strict=True))
            ]
        )
        if topics:
            overview = await self._deps.intelligence.overview(topics, profile)
        else:
            overview = DigestOverview(title=f"Дайджест для профиля «{profile.name}»")
        return {
            "overview": overview.model_dump(mode="json"),
            "topics": [topic.model_dump(mode="json") for topic in topics],
        }

    async def persist(self, state: DigestState) -> dict[str, Any]:
        _emit("persist")
        graded = [
            GradedCandidate.model_validate(item)
            for item in state.get("personalized", state.get("graded", []))
        ]
        topics = [Topic.model_validate(topic) for topic in state["topics"]]
        overview = DigestOverview.model_validate(state["overview"])
        await self._deps.store.save(
            state["digest_id"],
            overview=overview,
            topics=topics,
            graded=graded,
            rejected={int(key): value for key, value in state.get("rejected", {}).items()},
            stats=_stats(state, self._deps, graded, topics, overview),
        )
        return {}


def build_graph(deps: PipelineDeps) -> StateGraph[DigestState]:
    nodes = DigestNodes(deps)
    graph = StateGraph(DigestState)
    graph.add_node("prepare", nodes.prepare, retry_policy=_IO_RETRY)
    graph.add_node("retrieve", nodes.retrieve, retry_policy=_IO_RETRY)
    graph.add_node("grade", nodes.grade, input_schema=GradeTask, timeout=MODEL_NODE_TIMEOUT)
    graph.add_node("select", nodes.select_items, retry_policy=_IO_RETRY)
    graph.add_node("cluster", nodes.cluster, retry_policy=_IO_RETRY)
    graph.add_node(
        "summarize", nodes.summarize, input_schema=SummaryTask, timeout=MODEL_NODE_TIMEOUT
    )
    graph.add_node(
        "name_topic", nodes.name_topic, input_schema=TopicTask, timeout=MODEL_NODE_TIMEOUT
    )
    graph.add_node("compose", nodes.compose, timeout=MODEL_NODE_TIMEOUT)
    graph.add_node("persist", nodes.persist, retry_policy=_IO_RETRY)

    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "retrieve")
    graph.add_conditional_edges("retrieve", nodes.fan_out_grading, ["grade", "select"])
    graph.add_edge("grade", "select")
    graph.add_edge("select", "cluster")
    graph.add_conditional_edges(
        "cluster", nodes.fan_out_writing, ["summarize", "name_topic", "compose"]
    )
    graph.add_edge("summarize", "compose")
    graph.add_edge("name_topic", "compose")
    graph.add_edge("compose", "persist")
    graph.add_edge("persist", END)
    return graph


def _section(kind: RecordKind, items: list[SelectedItem]) -> Topic:
    """A fixed section of a specialist's digest, highest priority first."""
    ordered = sorted(
        items,
        key=lambda item: (PRIORITY_ORDER[priority(kind, item.text)], -item.graded.score),
    )
    return Topic(
        title=SECTION_TITLES[kind],
        overview=section_overview(kind, [item.text for item in ordered]),
        items=tuple(ordered),
    )


def _unique_titles(topics: list[Topic]) -> list[Topic]:
    """Two clusters may get the same name; number the repeats so they stay apart."""
    seen: dict[str, int] = {}
    result = []
    for topic in topics:
        count = seen.get(topic.title, 0) + 1
        seen[topic.title] = count
        title = topic.title if count == 1 else f"{topic.title} ({count})"
        result.append(topic.model_copy(update={"title": title}))
    return result


def _stats(
    state: DigestState,
    deps: PipelineDeps,
    graded: list[GradedCandidate],
    topics: list[Topic],
    overview: DigestOverview,
) -> dict[str, Any]:
    selected = [item for topic in topics for item in topic.items]
    model_expected = deps.llm_provider != "heuristic"
    graded_by_model = sum(1 for item in graded if item.grade.by_model)
    written_by_model = sum(1 for item in selected if item.text and item.text.by_model)
    # Excluded candidates are rejected without a model call, so they do not
    # count towards degradation.
    gradable = sum(1 for item in graded if item.candidate.excluded_by is None)
    priorities = [priority(item.graded.grade.kind, item.text) for item in selected]
    degraded = model_expected and (
        graded_by_model < gradable or written_by_model < len(selected) or not overview.by_model
    )
    return {
        "window_total": state.get("window_total", 0),
        "candidates": len(graded),
        "selected": len(selected),
        "topics": len(topics),
        "sources": len({item.article.source_name for item in selected}),
        "duplicates_merged": sum(len(item.duplicates) for item in selected),
        "kinds": {
            kind: sum(1 for item in selected if item.graded.grade.kind == kind)
            for kind in ("attack", "vulnerability", "news")
        },
        "priorities": {level: priorities.count(level) for level in ("high", "medium", "low")},
        # The check of entries against their articles: fields taken out, entries touched.
        "unsupported_fields": sum(len(item.text.unsupported) for item in selected if item.text),
        "entries_corrected": sum(1 for item in selected if item.text and item.text.unsupported),
        "embedded_now": state.get("embedded_now", 0),
        "lexical_only": state.get("lexical_only", False),
        "embedding_model": deps.embedder.model_id,
        "llm": deps.intelligence.name,
        "graded_by_model": graded_by_model,
        "written_by_model": written_by_model,
        "degraded": degraded,
        # Candidates whose score the reader's own behaviour moved.
        "personalized": sum(1 for item in graded if item.personal),
        "personalization_failed": any(item.personal_note == _UNPERSONALIZED for item in graded),
        # Interests that learned from the reader, as this digest used them.
        "adaptation": state.get("adaptation", {}),
        "duration_seconds": round(time.time() - state.get("started_at", time.time()), 1),
    }
