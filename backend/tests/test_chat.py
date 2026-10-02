"""The model connection: what goes to the server and what is accepted back."""

import json
from typing import Any

import httpx
import pytest
from ollama import ResponseError
from pydantic import BaseModel, Field, ValidationError

from radar.ai import llm
from radar.ai.llm import ChatTool, ModelChat, ollama_chat, openai_chat
from radar.config import Settings


class Verdict(BaseModel):
    relevance: int = Field(ge=0, le=3)
    reason: str


class Server:
    """An Ollama that gives the answers in turn and keeps what it was asked."""

    def __init__(self, *answers: str | dict[str, Any] | int) -> None:
        self.answers = list(answers)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        answer = self.answers.pop(0)
        # A number is an error status, as the cloud sends it.
        if isinstance(answer, int):
            return httpx.Response(answer, json={"error": "too many concurrent requests"})
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


def chat(server: Server, **options: Any) -> ModelChat:
    return ollama_chat(
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


async def test_a_busy_server_is_asked_again_after_a_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "RATE_LIMIT_PAUSE_SECONDS", 0.0)
    server = Server(429, 429, '{"relevance": 2, "reason": "по теме"}')

    verdict = await chat(server).ask(Verdict, "Оцени.", "Статья")

    # A full queue on the server is not the model failing: no breaker, no fallback.
    assert verdict == Verdict(relevance=2, reason="по теме")
    assert len(server.requests) == 3


async def test_a_server_that_stays_busy_or_breaks_fails_the_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(llm, "RATE_LIMIT_PAUSE_SECONDS", 0.0)
    busy = Server(*[429] * (llm.RATE_LIMIT_RETRIES + 1))
    broken = Server(500, '{"relevance": 2, "reason": "по теме"}')

    with pytest.raises(ResponseError):
        await chat(busy).ask(Verdict, "Оцени.", "Статья")
    with pytest.raises(ResponseError):
        await chat(broken).ask(Verdict, "Оцени.", "Статья")

    assert len(busy.requests) == llm.RATE_LIMIT_RETRIES + 1
    # Any other error goes to the breaker at once.
    assert len(broken.requests) == 1


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


class OpenAIServer:
    """An OpenAI-compatible Chat Completions server: answers in turn, keeps requests."""

    def __init__(self, *answers: str | dict[str, Any]) -> None:
        self.answers = list(answers)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        answer = self.answers.pop(0)
        message: dict[str, Any] = {"role": "assistant", "content": answer}
        if isinstance(answer, dict):
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": answer["name"],
                            "arguments": json.dumps(answer["arguments"]),
                        },
                    }
                ],
            }
        body = {
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "created": 0,
            "model": "qwen3.6-35b-a3b",
            "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        return httpx.Response(200, json=body)

    def body(self, index: int) -> dict[str, Any]:
        body: dict[str, Any] = json.loads(self.requests[index].content)
        return body


async def test_an_openai_compatible_server_gets_the_key_the_folder_and_no_schema_field() -> None:
    server = OpenAIServer(
        {"name": "lookup", "arguments": {"identifier": "CVE-2026-88772"}},
        '```json\n{"relevance": 3, "reason": "в каталоге KEV"}\n```',
    )

    async def lookup(arguments: dict[str, Any]) -> str:
        return "CVE-2026-88772: в каталоге CISA KEV с 27.09.2026: используется в атаках"

    tool = ChatTool({"type": "function", "function": {"name": "lookup", "parameters": {}}}, lookup)
    model = openai_chat(
        "gpt://b1g/qwen3.6-35b-a3b/latest",
        "https://llm.example/v1",
        api_key="secret",
        project="b1g",
        transport=httpx.MockTransport(server),
    )

    verdict = await model.ask(Verdict, "Оцени.", "Статья", (tool,))

    assert verdict == Verdict(relevance=3, reason="в каталоге KEV")
    first = server.requests[0]
    assert first.url.path == "/v1/chat/completions"
    assert first.headers["authorization"] == "Bearer secret"
    # Yandex AI Studio wants the folder id as the project.
    assert first.headers["openai-project"] == "b1g"
    assert server.body(0)["model"] == "gpt://b1g/qwen3.6-35b-a3b/latest"
    # Not every such server takes json_schema: the prompt carries the schema.
    assert "response_format" not in server.body(0)
    assert server.body(1)["messages"][-1]["role"] == "tool"
