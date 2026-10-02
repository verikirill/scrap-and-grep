"""Model-backed judgement and writing through Ollama and LangChain."""

import asyncio
import json
from collections.abc import Sequence
from typing import Any, Literal

import httpx
import json_repair
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from pydantic import BaseModel, ValidationError

from radar import cards
from radar.ai import prompts
from radar.ai.heuristic import extractive_summary
from radar.domain import (
    AttackCard,
    Candidate,
    DigestOverview,
    Grade,
    Interest,
    ItemSummary,
    ProfileSpec,
    SelectedItem,
    Topic,
    TopicName,
    VulnerabilityCard,
)
from radar.ingest.telegram import is_post_url
from radar.text import numbers

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


def _parsed[T: BaseModel](schema: type[T], answer: str) -> T:
    """The answer checked against its schema. JSON that is only broken, a
    missing comma or an unclosed bracket, is mended first: asking the model
    again costs a call, and measured on the cloud it broke the same way twice."""
    try:
        return schema.model_validate_json(answer)
    except ValidationError as error:
        if not any(problem["type"] == "json_invalid" for problem in error.errors()):
            raise
        return schema.model_validate(json_repair.loads(answer, skip_json_loads=True))


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
                return _parsed(schema, answer)
            except ValidationError as error:
                retry = [
                    *messages,
                    AIMessage(content=answer),
                    HumanMessage(
                        content=f"Ответ не подходит под схему: {_problems(error)}. "
                        "Верни исправленный JSON-объект."
                    ),
                ]
            return _parsed(schema, await self._answer(retry, shape))

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
            kind=out.kind,
            by_model=True,
        )

    async def summarize(
        self, item: SelectedItem, profile: ProfileSpec, interest: Interest | None
    ) -> ItemSummary:
        """A card for a specialist's attack or vulnerability, a brief for
        management, a plain entry otherwise; then checked against the article.

        A figure in the prose that the article does not have is sent back once;
        if it stays, that part of the entry is replaced by the article's own text.
        The card itself is checked later, in the graph, after the answer cache.
        """
        article = item.article
        schema, system = prompts.writing_task(item.graded.grade.kind, profile.audience)
        prompt = prompts.summary_prompt(item, profile, interest)
        source = cards.source_text(article.title, article.summary, article.content)
        # "Почему важно" may borrow a figure from the reader's own profile: "187-ФЗ".
        allowed = (
            numbers(source)
            | numbers(prompts.reader_text(profile, interest))
            | {str(article.published_at.year)}
        )
        out = await self._ask(schema, system, prompt)
        stray = _stray_figures(out, allowed)
        if stray:
            out = await self._ask(schema, system, prompts.with_stray_note(prompt, stray))
            stray = _stray_figures(out, allowed)
        return _entry(out, item, stray)

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


def _stray_figures(out: prompts.SummaryOut, allowed: set[str]) -> set[str]:
    return cards.unsupported_figures(f"{out.headline} {out.summary} {out.why}", allowed)


def _entry(out: prompts.SummaryOut, item: SelectedItem, stray: set[str]) -> ItemSummary:
    """The model's answer as an entry; prose with a figure the article lacks
    gives way to the article's own text."""
    article = item.article
    unsupported = []
    # A Russian headline is kept verbatim: rewording it can only drift from
    # what the source said. The model's headline translates, and names a
    # Telegram post, whose "title" is just its first line cut short.
    own_title = article.language == "ru" and not is_post_url(article.url)
    headline = (not own_title and out.headline.strip()) or article.title
    if numbers(headline) & stray:
        headline = article.title
    summary = out.summary.strip()
    if numbers(summary) & stray:
        summary = extractive_summary(article)
        unsupported.append("Пересказ")
    why = out.why.strip()
    if numbers(why) & stray:
        why = ""
        unsupported.append("Почему важно")
    return ItemSummary(
        headline=headline,
        summary=summary,
        why=why,
        by_model=True,
        attack=_attack(out) if isinstance(out, prompts.AttackOut) else None,
        vulnerability=(_vulnerability(out) if isinstance(out, prompts.VulnerabilityOut) else None),
        tags=tuple(dict.fromkeys(out.tags)) if isinstance(out, prompts.BriefOut) else (),
        unsupported=tuple(unsupported),
    )


def _attack(out: prompts.AttackOut) -> AttackCard:
    return AttackCard(
        victim_country=out.victim_country.strip(),
        victim_in_russia=out.victim_in_russia,
        group=out.group.strip(),
        attack_date=out.attack_date.strip(),
        sectors=out.sectors.strip(),
        energy_sector=out.energy_sector,
        initial_access=out.initial_access.strip(),
        tools=tuple(dict.fromkeys(tool.strip()[:80] for tool in out.tools if tool.strip())),
        vulnerabilities=tuple(out.vulnerabilities),
        iocs=out.iocs,
    )


def _vulnerability(out: prompts.VulnerabilityOut) -> VulnerabilityCard:
    return VulnerabilityCard(
        name=out.name.strip(),
        affected=out.affected.strip(),
        fix=out.fix.strip(),
        workaround=out.workaround.strip(),
        exploit=out.exploit,
        ids=tuple(out.ids),
        cvss_score=f"{out.cvss_score:g}" if out.cvss_score is not None else "",
        cvss_vector=out.cvss_vector.strip(),
        impact=out.impact.strip(),
    )
