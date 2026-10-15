"""Embeddings from an OpenAI-compatible server: what goes out and what is kept."""

import json
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from radar.ai import embedder as embedder_module
from radar.ai import factory
from radar.ai.embedder import OpenAIEmbedder, _Pace
from radar.config import EMBEDDING_DIM, Settings

DOC = "emb://b1gfolder/text-embeddings-v2-doc/latest"
QUERY = "emb://b1gfolder/text-embeddings-v2-query/latest"


class Server:
    """An /embeddings endpoint that answers in turn and keeps what it was asked.

    A number among the answers is an error status; otherwise the vector is
    [position of the request, length of the input], so that order can be checked.
    """

    def __init__(self, *statuses: int) -> None:
        self.statuses = list(statuses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.statuses:
            return httpx.Response(self.statuses.pop(0), json={"error": "quota"})
        text = self.body(len(self.requests) - 1)["input"]
        vector = [float(len(self.requests)), float(len(text))]
        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": [{"object": "embedding", "index": 0, "embedding": vector}],
            },
        )

    def body(self, index: int) -> dict[str, Any]:
        body: dict[str, Any] = json.loads(self.requests[index].content)
        return body


def yandex(server: Server, **options: Any) -> OpenAIEmbedder:
    return OpenAIEmbedder(
        DOC,
        "https://ai.api.cloud.yandex.net/v1/",
        query_model=QUERY,
        api_key="secret",
        project="b1gfolder",
        requests_per_second=1000.0,
        transport=httpx.MockTransport(server),
        **options,
    )


async def test_every_text_goes_alone_to_the_model_of_its_kind() -> None:
    server = Server()
    model = yandex(server, dimensions=768)

    documents = await model.embed(["ПЛК Siemens", "SCADA"], "document")
    (query,) = await model.embed(["безопасность АСУ ТП"], "query")

    # Yandex takes one string per request, not a list.
    assert [server.body(index)["input"] for index in range(3)] == [
        "ПЛК Siemens",
        "SCADA",
        "безопасность АСУ ТП",
    ]
    assert [server.body(index)["model"] for index in range(3)] == [DOC, DOC, QUERY]
    assert all(server.body(index)["dimensions"] == 768 for index in range(3))
    request = server.requests[0]
    assert request.method == "POST"
    assert request.url.path == "/v1/embeddings"
    assert request.headers["authorization"] == "Bearer secret"
    # The folder id is the project, as for Yandex's chat models.
    assert request.headers["openai-project"] == "b1gfolder"
    # Every text keeps its own vector, padded to the stored width.
    assert [vector[1] for vector in documents] == [11.0, 5.0]
    assert all(len(vector) == EMBEDDING_DIM for vector in [*documents, query])
    assert query[2:] == [0.0] * (EMBEDDING_DIM - 2)
    assert model.requests == 3


async def test_a_local_server_gets_no_key_no_project_and_no_width() -> None:
    server = Server()
    model = OpenAIEmbedder("bge-m3", "http://vllm:8000/v1", transport=httpx.MockTransport(server))

    await model.embed(["запрос"], "query")

    assert "authorization" not in server.requests[0].headers
    assert "openai-project" not in server.requests[0].headers
    # Without a model of its own the query goes to the model of the documents.
    assert server.body(0) == {"model": "bge-m3", "input": "запрос"}


def test_vectors_are_kept_under_the_model_and_width_without_the_folder() -> None:
    server = Server()

    # A move to another folder must not make every article embedded again,
    # and vectors of another width are other vectors.
    assert yandex(server).model_id == "openai:text-embeddings-v2-doc/latest"
    assert yandex(server, dimensions=768).model_id == "openai:text-embeddings-v2-doc/latest@768"


async def test_a_text_beyond_the_input_limit_is_cut() -> None:
    server = Server()

    await yandex(server).embed(["а" * 20_000], "document")

    assert len(server.body(0)["input"]) == embedder_module.OPENAI_EMBED_MAX_CHARS


async def test_a_full_quota_is_waited_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(embedder_module, "OPENAI_EMBED_PAUSE_SECONDS", 0.0)
    server = Server(429, 429)

    (vector,) = await yandex(server).embed(["SCADA"], "document")

    assert vector[1] == 5.0
    assert len(server.requests) == 3


async def test_a_quota_that_stays_full_or_an_error_fails_the_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(embedder_module, "OPENAI_EMBED_PAUSE_SECONDS", 0.0)
    busy = Server(*[429] * (embedder_module.OPENAI_EMBED_RETRIES + 1))
    broken = Server(401)

    with pytest.raises(httpx.HTTPStatusError):
        await yandex(busy).embed(["SCADA"], "document")
    with pytest.raises(httpx.HTTPStatusError):
        await yandex(broken).embed(["SCADA"], "document")

    assert len(busy.requests) == embedder_module.OPENAI_EMBED_RETRIES + 1
    # A wrong key is not a queue: no retries.
    assert len(broken.requests) == 1


def test_requests_start_no_closer_than_the_rate_allows(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [100.0]
    monkeypatch.setattr("radar.ai.embedder.time.monotonic", lambda: clock[0])
    pace = _Pace(10.0)

    # Three requests at once: the second waits 0.1 s, the third 0.2 s.
    assert [pace.delay() for _ in range(3)] == pytest.approx([0.0, 0.1, 0.2])
    # After a quiet second the next one goes at once.
    clock[0] = 101.0
    assert pace.delay() == 0.0


def test_the_provider_is_built_from_the_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        _env_file=None,
        embedding_provider="openai",
        embedding_base_url="https://ai.api.cloud.yandex.net/v1",
        embedding_model=DOC,
        embedding_query_model=QUERY,
        embedding_api_key="secret",
        embedding_project="b1gfolder",
        embedding_dimensions="",
    )
    monkeypatch.setattr(factory, "get_settings", lambda: settings)
    factory.get_embedder.cache_clear()
    try:
        built = factory.get_embedder()
    finally:
        factory.get_embedder.cache_clear()

    assert isinstance(built, OpenAIEmbedder)
    assert built.model_id.startswith("openai:text-embeddings-v2-doc/latest")
    # Compose passes an unset width as an empty string.
    assert settings.embedding_dimensions is None
    preset = factory.embedding_preset("text-embeddings-v2-doc/latest")
    assert built.duplicate_threshold == preset.duplicate_threshold
    assert built.search_floor == preset.search_floor


def test_openai_embeddings_without_an_address_stop_the_start() -> None:
    with pytest.raises(ValidationError, match="RADAR_EMBEDDING_BASE_URL"):
        Settings(_env_file=None, embedding_provider="openai")
