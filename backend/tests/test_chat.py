"""The model connection: what goes to the server and what is accepted back."""

import json
from typing import Any

import httpx
import pytest
from pydantic import BaseModel, Field, ValidationError

from radar.ai.ollama import ChatTool, OllamaChat
from radar.config import Settings


class Verdict(BaseModel):
    relevance: int = Field(ge=0, le=3)
    reason: str


class Server:
    """An Ollama that gives the answers in turn and keeps what it was asked."""

    def __init__(self, *answers: str | dict[str, Any]) -> None:
        self.answers = list(answers)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        answer = self.answers.pop(0)
        # A dict is a tool call: {"name": ..., "arguments": {...}}.
        calls = [{"function": answer}] if isinstance(answer, dict) else []
        line = {
            "model": "gpt-oss:120b",
            "created_at": "2026-10-02T10:00:00Z",
            "message": {
                "role": "assistant",
                "content": "" if calls else answer,
                "thinking": "The reader wants JSON.",
                "tool_calls": calls,
            },
            "done": True,
            "done_reason": "stop",
        }
        return httpx.Response(200, text=json.dumps(line, ensure_ascii=False) + "\n")

    def body(self, index: int) -> dict[str, Any]:
        body: dict[str, Any] = json.loads(self.requests[index].content)
        return body


def chat(server: Server, **options: Any) -> OllamaChat:
    return OllamaChat(
        "gpt-oss:120b", "https://ollama.com", transport=httpx.MockTransport(server), **options
    )


async def test_the_cloud_gets_the_key_the_reasoning_level_and_the_schema() -> None:
    hyphen = chr(0x2011)
    cve = f"CVE{hyphen}2025{hyphen}40566"
    server = Server(f'```json\n{{"relevance": 3, "reason": "{cve} в ПЛК"}}\n```')

    verdict = await chat(server, api_key="secret", reasoning="low").ask(Verdict, "Оцени.", "Статья")

    # Out of the fence, with plain hyphens: a search for the CVE finds it.
    assert verdict == Verdict(relevance=3, reason="CVE-2025-40566 в ПЛК")
    assert server.requests[0].headers["authorization"] == "Bearer secret"
    body = server.body(0)
    assert body["think"] == "low"
    assert body["format"] == Verdict.model_json_schema()
    # The cloud ignores `format`, so the prompt asks for the shape itself.
    assert '"relevance"' in body["messages"][0]["content"]


async def test_a_local_model_gets_no_key_and_no_reasoning() -> None:
    server = Server('{"relevance": 1, "reason": "косвенно"}')

    await chat(server).ask(Verdict, "Оцени.", "Статья")

    assert "authorization" not in server.requests[0].headers
    assert server.body(0)["think"] is False


async def test_an_answer_off_the_schema_goes_back_once_with_what_is_wrong() -> None:
    server = Server("**Релевантность: 3** - уязвимость в ПЛК.", '{"relevance": 3, "reason": "ПЛК"}')

    verdict = await chat(server, reasoning="low").ask(Verdict, "Оцени.", "Статья")

    assert verdict == Verdict(relevance=3, reason="ПЛК")
    *_, answer, note = server.body(1)["messages"]
    assert answer["role"] == "assistant"
    assert "Релевантность" in answer["content"]
    assert note["role"] == "user"
    assert "не подходит под схему" in note["content"]


async def test_a_second_answer_off_the_schema_fails_and_the_breaker_takes_over() -> None:
    server = Server('{"relevance": 7, "reason": "x"}', '{"relevance": 9, "reason": "x"}')

    with pytest.raises(ValidationError):
        await chat(server).ask(Verdict, "Оцени.", "Статья")

    assert len(server.requests) == 2
    assert (
        "relevance: Input should be less than or equal to 3"
        in (server.body(1)["messages"][-1]["content"])
    )


def test_a_cloud_model_without_a_key_stops_the_start() -> None:
    with pytest.raises(ValidationError, match="RADAR_LLM_API_KEY"):
        Settings(llm_provider="ollama", llm_base_url="https://ollama.com", llm_api_key=None)
    # Offline and local models need no key.
    Settings(llm_provider="heuristic", llm_api_key=None)
    Settings(llm_provider="ollama", llm_base_url="", llm_api_key=None)


async def test_json_that_is_only_broken_is_mended_without_asking_again() -> None:
    # A missing comma, as gpt-oss once wrote a list of highlights.
    server = Server('{"relevance": 2 "reason": "по теме"}')

    verdict = await chat(server).ask(Verdict, "Оцени.", "Статья")

    assert verdict == Verdict(relevance=2, reason="по теме")
    assert len(server.requests) == 1


async def test_the_model_calls_its_tool_and_answers_with_what_it_got() -> None:
    server = Server(
        {"name": "lookup", "arguments": {"identifier": "CVE-2026-88772"}},
        '{"relevance": 3, "reason": "в каталоге KEV"}',
    )
    asked: list[dict[str, Any]] = []

    async def lookup(arguments: dict[str, Any]) -> str:
        asked.append(arguments)
        return "CVE-2026-88772: в каталоге CISA KEV с 27.09.2026: используется в атаках"

    tool = ChatTool(
        {
            "type": "function",
            "function": {
                "name": "lookup",
                "description": "Справка об уязвимости",
                "parameters": {
                    "type": "object",
                    "properties": {"identifier": {"type": "string"}},
                    "required": ["identifier"],
                },
            },
        },
        lookup,
    )

    verdict = await chat(server).ask(Verdict, "Оцени.", "Статья", (tool,))

    assert verdict == Verdict(relevance=3, reason="в каталоге KEV")
    assert asked == [{"identifier": "CVE-2026-88772"}]
    first, second = server.body(0), server.body(1)
    assert first["tools"][0]["function"]["name"] == "lookup"
    # No schema while the model may still call a tool: it would leave no room for the call.
    assert first.get("format") is None
    assert second["messages"][-1]["role"] == "tool"
    assert "CISA KEV" in second["messages"][-1]["content"]


async def test_a_tool_that_fails_is_told_to_the_model_not_raised() -> None:
    server = Server(
        {"name": "lookup", "arguments": {"identifier": "CVE-2026-1"}},
        '{"relevance": 2, "reason": "по тексту"}',
    )

    async def broken(arguments: dict[str, Any]) -> str:
        raise ConnectionError("database went away")

    tool = ChatTool({"type": "function", "function": {"name": "lookup", "parameters": {}}}, broken)

    verdict = await chat(server).ask(Verdict, "Оцени.", "Статья", (tool,))

    assert verdict.relevance == 2
    assert "недоступна" in server.body(1)["messages"][-1]["content"]
