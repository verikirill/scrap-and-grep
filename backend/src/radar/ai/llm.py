"""Model-backed judgement and writing through LangChain: Ollama or an OpenAI-compatible server."""

import asyncio
import json
import random
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import httpx
import json_repair
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import Runnable
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, SecretStr, ValidationError

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
    VulnerabilityReference,
)
from radar.ingest.telegram import is_post_url
from radar.logging import get_logger
from radar.text import numbers

log = get_logger(__name__)

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


# Rounds of tool calls before the model must answer, and calls in one round.
MAX_TOOL_ROUNDS = 2
MAX_TOOL_CALLS = 4

# A server that is full answers 429. That is a queue, not a failure: the
# request waits and goes again before the breaker hears of it. Measured on
# Ollama's cloud, where nemotron-3-nano takes fewer parallel requests than four.
RATE_LIMIT_RETRIES = 3
RATE_LIMIT_PAUSE_SECONDS = 2.0


def _rate_limited(error: BaseException) -> bool:
    """A 429 from Ollama's client or from an OpenAI-compatible server."""
    return getattr(error, "status_code", None) == 429


@dataclass(frozen=True, slots=True)
class ChatTool:
    """A function the model may call while it writes: its description in
    the OpenAI form Ollama takes, and what runs when it is called."""

    spec: dict[str, Any]
    call: Callable[[dict[str, Any]], Awaitable[str]]

    @property
    def name(self) -> str:
        return str(self.spec["function"]["name"])


async def _run(tool: ChatTool | None, arguments: Any) -> str:
    """A tool's answer; a failure is told to the model, not raised: a database
    hiccup in a lookup must not count as the model failing and trip the breaker."""
    if tool is None:
        return "Такого инструмента нет."
    try:
        return await tool.call(arguments if isinstance(arguments, dict) else {})
    except Exception as exc:
        log.warning("tool_failed", tool=tool.name, error=f"{type(exc).__name__}: {exc}"[:300])
        return "Справка сейчас недоступна, ответь по тексту публикации."


class ModelChat:
    """One schema-constrained question to the model. Shared by every step that
    talks to it, so the concurrency bound covers them all.

    The model behind it is any LangChain chat model: Ollama, local or in its
    cloud, or an OpenAI-compatible server such as Yandex AI Studio or vLLM.
    The schema goes both ways. Ollama holds the answer to it as `format`
    where it can; the cloud takes the field and ignores it, and gpt-oss there
    answers in markdown unless the prompt itself asks for JSON. So the prompt
    carries the schema too, the answer is checked here, and one that does not
    fit is sent back once with what is wrong in it. That is also all an
    OpenAI-compatible server is asked for: not every one takes `json_schema`.
    """

    def __init__(
        self,
        llm: BaseChatModel,
        name: str,
        *,
        schema_field: str | None = None,
        concurrency: int = 4,
        timeout: float = 120.0,
    ) -> None:
        self.name = name
        self._llm = llm
        # The request field that holds the reply to the schema, where there is one.
        self._schema_field = schema_field
        # A server queues requests beyond its own limit; bounding them here
        # keeps the queue short and the timeouts honest.
        self._slots = asyncio.Semaphore(concurrency)
        self._timeout = timeout

    async def ask[T: BaseModel](
        self, schema: type[T], system: str, user: str, tools: Sequence[ChatTool] = ()
    ) -> T:
        shape = schema.model_json_schema()
        messages: list[BaseMessage] = [
            SystemMessage(content=f"{system}\n\n{_answer_format(shape)}"),
            HumanMessage(content=user),
        ]
        async with self._slots:
            messages, answer = await self._with_tools(messages, tools)
            if answer is None:
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

    async def _with_tools(
        self, messages: list[BaseMessage], tools: Sequence[ChatTool]
    ) -> tuple[list[BaseMessage], str | None]:
        """Let the model call its tools; the answer if it gave one along the way.

        No `format` here: a local Ollama would hold the reply to the answer's
        schema and leave no room for a call.
        """
        if not tools:
            return messages, None
        by_name = {tool.name: tool for tool in tools}
        model = self._llm.bind_tools([tool.spec for tool in tools])
        for _ in range(MAX_TOOL_ROUNDS):
            reply = await self._invoke(model, messages)
            if not reply.tool_calls:
                return messages, _json_text(reply.text)
            results: list[BaseMessage] = []
            for index, call in enumerate(reply.tool_calls):
                # Every call is answered: some chat templates expect a result per call.
                result = (
                    await _run(by_name.get(call["name"]), call["args"])
                    if index < MAX_TOOL_CALLS
                    else "Лимит вызовов исчерпан: ответь по уже полученным сведениям."
                )
                results.append(ToolMessage(content=result, tool_call_id=call["id"] or call["name"]))
            messages = [*messages, reply, *results]
        return messages, None

    async def _answer(self, messages: list[BaseMessage], shape: dict[str, Any]) -> str:
        # The clock starts once a slot is free: time spent queueing behind
        # other calls is not the model being slow and must not trip the breaker.
        model = self._llm.bind(**{self._schema_field: shape}) if self._schema_field else self._llm
        reply = await self._invoke(model, messages)
        return _json_text(reply.text)

    async def _invoke[R](self, model: Runnable[Any, R], messages: list[BaseMessage]) -> R:
        """One request; a full server is asked again after a growing pause.
        The slot stays taken meanwhile, which is what a full server needs."""
        for attempt in range(RATE_LIMIT_RETRIES):
            try:
                async with asyncio.timeout(self._timeout):
                    return await model.ainvoke(messages)
            except Exception as error:
                if not _rate_limited(error):
                    raise
            # Spread out, so the requests that were refused together do not return together.
            pause = RATE_LIMIT_PAUSE_SECONDS * 2**attempt * random.uniform(0.5, 1.5)  # noqa: S311
            log.info("llm_busy", model=self.name, attempt=attempt + 1, pause=round(pause, 1))
            await asyncio.sleep(pause)
        async with asyncio.timeout(self._timeout):
            return await model.ainvoke(messages)


def ollama_chat(
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
) -> ModelChat:
    """A model of a local Ollama or of Ollama's cloud."""
    llm = ChatOllama(
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
    return ModelChat(
        llm,
        f"ollama:{model}",
        schema_field="format",
        concurrency=concurrency,
        timeout=timeout,
    )


def openai_chat(
    model: str,
    base_url: str,
    *,
    api_key: str | None = None,
    project: str = "",
    reasoning: Literal["off", "low", "medium", "high"] = "off",
    temperature: float = 0.1,
    concurrency: int = 4,
    timeout: float = 120.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ModelChat:
    """A model behind an OpenAI-compatible Chat Completions API: Yandex AI
    Studio (the project is the folder id), vLLM, Ollama's /v1."""
    llm = ChatOpenAI(
        model=model,
        base_url=base_url,
        # A local vLLM takes any key; the client wants one all the same.
        api_key=SecretStr(api_key or "not-needed"),
        temperature=temperature,
        reasoning_effort=None if reasoning == "off" else reasoning,
        default_headers={"OpenAI-Project": project} if project else None,
        # Chat Completions, not the Responses API: that is what such servers share.
        use_responses_api=False,
        timeout=timeout,
        # The circuit breaker decides about retries; the client must not wait them out.
        max_retries=1,
        http_async_client=httpx.AsyncClient(transport=transport) if transport else None,
    )
    return ModelChat(llm, f"openai:{model}", concurrency=concurrency, timeout=timeout)


# Looks vulnerabilities up in the reference bases by their ids.
Lookup = Callable[[Sequence[str]], Awaitable[list[VulnerabilityReference]]]


class ModelIntelligence:
    def __init__(self, chat: ModelChat, lookup: Lookup | None = None) -> None:
        self.name = chat.name
        self._ask = chat.ask
        self._lookup = lookup

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
        found: list[VulnerabilityReference] = []
        # Only a card has ids to look up: a brief and a plain entry do not.
        carded = schema in (prompts.AttackOut, prompts.VulnerabilityOut)
        tools = self._tools(found) if carded else ()
        if tools:
            system = f"{system}\n\n{prompts.LOOKUP_NOTE}"
        out = await self._ask(schema, system, prompt, tools)
        # What the bases said may stand in the card: a CVSS score from the BDU.
        allowed |= numbers(" ".join(reference.text() for reference in found))
        stray = _stray_figures(out, allowed)
        if stray:
            out = await self._ask(schema, system, prompts.with_stray_note(prompt, stray), tools)
            stray = _stray_figures(out, allowed)
        entry = _entry(out, item, stray)
        references = {reference.id: reference for reference in found}
        return entry.model_copy(update={"references": tuple(references.values())})

    def _tools(self, found: list[VulnerabilityReference]) -> tuple[ChatTool, ...]:
        """The lookup in the reference bases, as a tool the model calls; what
        it returned is kept for the entry."""
        lookup = self._lookup
        if lookup is None:
            return ()

        async def call(arguments: dict[str, Any]) -> str:
            identifier = str(arguments.get("identifier", ""))[:40]
            references = await lookup([identifier])
            found.extend(reference.model_copy(update={"via": "model"}) for reference in references)
            if not references:
                return f"«{identifier}» не похож на идентификатор CVE или БДУ."
            return "\n".join(reference.text() for reference in references)

        return (ChatTool(prompts.LOOKUP_TOOL, call),)

    async def name_topic(self, items: Sequence[SelectedItem], profile: ProfileSpec) -> TopicName:
        out = await self._ask(prompts.TopicOut, prompts.TOPIC_SYSTEM, prompts.topic_prompt(items))
        return TopicName(
            title=out.title.strip().strip('«»".'), overview=out.overview.strip(), by_model=True
        )

    async def overview(self, topics: Sequence[Topic], profile: ProfileSpec) -> DigestOverview:
        """The issue's title and key points. A figure the entries do not have,
        a year the model made up most of all, goes back once; a title that
        keeps it gives way to the first topic's, a key point is left out."""
        prompt = prompts.overview_prompt(topics, profile)
        allowed = numbers(
            " ".join(
                f"{item.article.title} {item.text.headline} {item.text.summary}"
                if item.text
                else item.article.title
                for topic in topics
                for item in topic.items
            )
        )
        out = await self._ask(prompts.OverviewOut, prompts.OVERVIEW_SYSTEM, prompt)
        stray = cards.unsupported_figures(f"{out.title} {' '.join(out.highlights)}", allowed)
        if stray:
            note = prompts.with_stray_note(prompt, stray)
            out = await self._ask(prompts.OverviewOut, prompts.OVERVIEW_SYSTEM, note)
        title = out.title.strip().strip('«»".')
        if cards.unsupported_figures(title, allowed):
            title = topics[0].title if topics else title
        return DigestOverview(
            title=title,
            highlights=tuple(
                line.strip()
                for line in out.highlights
                if line.strip() and not cards.unsupported_figures(line, allowed)
            ),
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
