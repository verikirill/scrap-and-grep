"""Model-backed judgement and writing through Ollama and LangChain."""

import asyncio
from collections.abc import Sequence
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from pydantic import BaseModel

from radar.ai import prompts
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


class OllamaIntelligence:
    def __init__(
        self,
        model: str,
        base_url: str,
        *,
        temperature: float = 0.1,
        num_ctx: int = 8192,
        keep_alive: str = "30m",
        concurrency: int = 4,
        timeout: float = 120.0,
    ) -> None:
        self.name = f"ollama:{model}"
        self._llm = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=temperature,
            num_ctx=num_ctx,
            keep_alive=keep_alive,
            # Hidden reasoning multiplies latency for batch grading and adds
            # nothing to a schema-constrained answer.
            reasoning=False,
            client_kwargs={"timeout": timeout},
        )
        # Ollama queues requests beyond OLLAMA_NUM_PARALLEL; bounding them here
        # keeps the queue short and the timeouts honest.
        self._slots = asyncio.Semaphore(concurrency)

    async def _ask[T: BaseModel](self, schema: type[T], system: str, user: str) -> T:
        chain = self._llm.with_structured_output(schema, method="json_schema")
        async with self._slots:
            result: Any = await chain.ainvoke(
                [SystemMessage(content=system), HumanMessage(content=user)]
            )
        return schema.model_validate(result)

    async def grade(self, candidate: Candidate, profile: ProfileSpec) -> Grade:
        out = await self._ask(
            prompts.GradeOut, prompts.GRADE_SYSTEM, prompts.grade_prompt(candidate, profile)
        )
        known = {interest.id for interest in profile.interests}
        return Grade(
            relevance=out.relevance,
            interest_id=out.interest_id if out.interest_id in known else candidate.interest_id,
            reason=out.reason.strip(),
            by_model=True,
        )

    async def summarize(
        self, item: SelectedItem, profile: ProfileSpec, interest: Interest | None
    ) -> ItemSummary:
        out = await self._ask(
            prompts.SummaryOut,
            prompts.SUMMARY_SYSTEM,
            prompts.summary_prompt(item, profile, interest),
        )
        return ItemSummary(
            headline=out.headline.strip() or item.article.title,
            summary=out.summary.strip(),
            why=out.why.strip(),
            by_model=True,
        )

    async def name_topic(self, items: Sequence[SelectedItem], profile: ProfileSpec) -> TopicName:
        out = await self._ask(prompts.TopicOut, prompts.TOPIC_SYSTEM, prompts.topic_prompt(items))
        return TopicName(
            title=out.title.strip().strip('«»".'), overview=out.overview.strip(), by_model=True
        )

    async def overview(self, topics: Sequence[Topic], profile: ProfileSpec) -> DigestOverview:
        out = await self._ask(
            prompts.OverviewOut, prompts.OVERVIEW_SYSTEM, prompts.overview_prompt(topics, profile)
        )
        return DigestOverview(
            title=out.title.strip().strip('«»".'),
            highlights=tuple(line.strip() for line in out.highlights if line.strip()),
            by_model=True,
        )
