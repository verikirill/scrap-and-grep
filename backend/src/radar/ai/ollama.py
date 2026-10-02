"""Model-backed judgement and writing through Ollama and LangChain."""

import asyncio
import json
from collections.abc import Sequence
from typing import Any, Literal

import httpx
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from pydantic import BaseModel, ValidationError

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

# Typographic hyphens and narrow spaces gpt-oss puts even into identifiers:
# CVE-2025-40566 written with U+2011 hyphens is not found by a search for the plain one.
_PLAIN = str.maketrans({"\u2010": "-", "\u2011": "-", "\u00a0": " ", "\u202f": " "})


def _answer_format(schema: dict[str, Any]) -> str:
    return (
        "Ответь одним JSON-объектом без markdown и пояснений вокруг, по этой JSON Schema:\n"
        + json.dumps(schema, ensure_ascii=False)
    )


def _json_text(content: str) -> str:
    """The object in an answer that wrapped it in a markdown fence or a sentence."""
    text = content.translate(_PLAIN).strip()
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if 0 <= start < end else text


def _problems(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(map(str, problem['loc'])) or 'ответ'}: {problem['msg']}"
        for problem in error.errors()[:5]
    )


class OllamaChat:
    """One schema-constrained question to the model. Shared by every step that
    talks to it, so the concurrency bound covers them all.

    The schema goes both ways. A local Ollama holds the answer to it as
    `format`; the cloud takes the field and ignores it, and gpt-oss there
    answers in markdown unless the prompt itself asks for JSON. So the prompt
    carries the schema too, the answer is checked here, and one that does not
    fit is sent back once with what is wrong in it.
    """

    def __init__(
        self,
        model: str,
        base_url: str,
        *,
        api_key: str | None = None,
        reasoning: Literal["off", "low", "medium", "high"] = "off",
        temperature: float = 0.1,
        num_ctx: int = 8192,
        keep_alive: int = 1800,
        concurrency: int = 4,
        timeout: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.name = f"ollama:{model}"
        self._llm = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=temperature,
            num_ctx=num_ctx,
            keep_alive=keep_alive,
            # Hidden reasoning multiplies latency for batch grading. A model
            # that has it built in, as gpt-oss, gets the lowest level instead.
            reasoning=False if reasoning == "off" else reasoning,
            # The key goes to this server only, not to the Ollama of the embeddings.
            client_kwargs={
                "timeout": timeout,
                "headers": {"Authorization": f"Bearer {api_key}"} if api_key else {},
            },
            async_client_kwargs={"transport": transport} if transport else {},
        )
        # Ollama queues requests beyond OLLAMA_NUM_PARALLEL; bounding them here
        # keeps the queue short and the timeouts honest.
        self._slots = asyncio.Semaphore(concurrency)
        self._timeout = timeout

    async def ask[T: BaseModel](self, schema: type[T], system: str, user: str) -> T:
        shape = schema.model_json_schema()
        messages: list[BaseMessage] = [
            SystemMessage(content=f"{system}\n\n{_answer_format(shape)}"),
            HumanMessage(content=user),
        ]
        async with self._slots:
            answer = await self._answer(messages, shape)
            try:
                return schema.model_validate_json(answer)
            except ValidationError as error:
                retry = [
                    *messages,
                    AIMessage(content=answer),
                    HumanMessage(
                        content=f"Ответ не подходит под схему: {_problems(error)}. "
                        "Верни исправленный JSON-объект."
                    ),
                ]
            return schema.model_validate_json(await self._answer(retry, shape))

    async def _answer(self, messages: list[BaseMessage], shape: dict[str, Any]) -> str:
        # The clock starts once a slot is free: time spent queueing behind
        # other calls is not the model being slow and must not trip the breaker.
        async with asyncio.timeout(self._timeout):
            reply = await self._llm.ainvoke(messages, format=shape)
        return _json_text(reply.text)


class OllamaIntelligence:
    def __init__(self, chat: OllamaChat) -> None:
        self.name = chat.name
        self._ask = chat.ask

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
        # A Russian headline is kept verbatim: rewording it can only drift from
        # what the source said. The model's headline is a translation aid.
        translated = item.article.language != "ru" and out.headline.strip()
        return ItemSummary(
            headline=translated or item.article.title,
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
