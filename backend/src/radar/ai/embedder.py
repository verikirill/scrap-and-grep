"""Text embedders behind one interface.

`HashingEmbedder` is the offline stand-in: a deterministic bag of character
n-grams. It knows nothing about meaning, but inflected forms of a word share
most of their n-grams, which is enough to rank Russian and English text by
lexical closeness without any model server.
"""

import asyncio
import math
import random
import re
import time
import zlib
from typing import Literal, Protocol

import httpx
import numpy as np

from radar.config import EMBEDDING_DIM
from radar.text import content_tokens

Kind = Literal["query", "document"]


class Embedder(Protocol):
    model_id: str
    # Cosine similarity above which two articles are treated as the same story.
    duplicate_threshold: float
    # Cosine below which a search query and an article are not about one thing.
    search_floor: float
    # False for embedders that only capture spelling. Their similarity cannot
    # carry a selection decision or a clustering on its own.
    semantic: bool

    async def embed(self, texts: list[str], kind: Kind) -> list[list[float]]: ...


def fit_dimension(vector: list[float], dim: int = EMBEDDING_DIM) -> list[float]:
    """Bring a vector to the stored width without changing cosine geometry.

    Zero-padding leaves every pairwise cosine intact. Truncation is only sound
    for Matryoshka-trained models and needs re-normalisation.
    """
    if len(vector) == dim:
        return vector
    if len(vector) < dim:
        return [*vector, *([0.0] * (dim - len(vector)))]
    head = np.asarray(vector[:dim], dtype=np.float32)
    norm = float(np.linalg.norm(head))
    return (head / norm).tolist() if norm else head.tolist()


class HashingEmbedder:
    """Feature hashing over word unigrams and character 3-5-grams."""

    duplicate_threshold = 0.72
    search_floor = 1.0
    semantic = False

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self._dim = dim
        self.model_id = f"hashing-ngram-v2-{dim}"

    async def embed(self, texts: list[str], kind: Kind) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = np.zeros(self._dim, dtype=np.float32)
        counts: dict[str, int] = {}
        for token in content_tokens(text):
            for feature in _features(token):
                counts[feature] = counts.get(feature, 0) + 1
        for feature, count in counts.items():
            digest = zlib.crc32(feature.encode("utf-8"))
            sign = 1.0 if digest & 1 else -1.0
            # Whole words weigh more than their fragments.
            weight = 2.0 if feature.startswith("w:") else 1.0
            vector[(digest >> 1) % self._dim] += sign * weight * (1.0 + math.log(count))
        norm = float(np.linalg.norm(vector))
        return (vector / norm).tolist() if norm else vector.tolist()


def _features(token: str) -> list[str]:
    padded = f"<{token}>"
    grams = [
        padded[start : start + size]
        for size in (3, 4, 5)
        for start in range(len(padded) - size + 1)
    ]
    return [f"w:{token}", *grams]


class OllamaEmbedder:
    """Embeddings served by Ollama through LangChain."""

    semantic = True

    def __init__(
        self,
        model: str,
        base_url: str,
        *,
        query_prefix: str = "",
        document_prefix: str = "",
        dimensions: int | None = None,
        duplicate_threshold: float = 0.88,
        search_floor: float = 0.0,
        keep_alive: int = 1800,
        batch_size: int = 32,
    ) -> None:
        from langchain_ollama import OllamaEmbeddings

        self.model_id = f"ollama:{model}"
        self.duplicate_threshold = duplicate_threshold
        self.search_floor = search_floor
        self._client = OllamaEmbeddings(
            model=model, base_url=base_url, keep_alive=keep_alive, dimensions=dimensions
        )
        self._prefix: dict[Kind, str] = {"query": query_prefix, "document": document_prefix}
        self._batch_size = batch_size

    async def embed(self, texts: list[str], kind: Kind) -> list[list[float]]:
        prefix = self._prefix[kind]
        prepared = [f"{prefix}{text}" for text in texts]
        vectors: list[list[float]] = []
        for start in range(0, len(prepared), self._batch_size):
            batch = await self._client.aembed_documents(prepared[start : start + self._batch_size])
            vectors.extend(fit_dimension(vector) for vector in batch)
        return vectors


# Yandex AI Studio takes one string per request and answers 10 requests a
# second per folder; its documents disagree on the input limit (2 048 or
# 8 192 tokens). An article is embedded as its title and 1 500 characters
# (store/articles.py), so the cut only guards against a text from elsewhere.
OPENAI_EMBED_MAX_CHARS = 6000
OPENAI_EMBED_IN_FLIGHT = 8
OPENAI_EMBED_RETRIES = 6
OPENAI_EMBED_PAUSE_SECONDS = 1.0
OPENAI_EMBED_MAX_PAUSE_SECONDS = 30.0
_URI_HEAD = re.compile(r"^[a-z]+://[^/]+/")


def short_model_name(model: str) -> str:
    """A model name without the folder of a Yandex URI:
    emb://<folder>/text-embeddings-v2-doc/latest -> text-embeddings-v2-doc/latest.
    Vectors are stored under the model's name, and a move to another folder
    must not make every article embedded again."""
    return _URI_HEAD.sub("", model)


class _Pace:
    """Spaces the starts of requests at least 1/rate seconds apart.

    No lock: the event loop runs one task at a time, so the slot is taken
    before anyone else looks. The embedder outlives an event loop in the
    tests and the CLI, and an asyncio lock would stay bound to the first.
    """

    def __init__(self, per_second: float) -> None:
        self._gap = 1.0 / per_second
        self._next = 0.0

    def delay(self) -> float:
        now = time.monotonic()
        start = max(now, self._next)
        self._next = start + self._gap
        return start - now


class OpenAIEmbedder:
    """Embeddings from an OpenAI-compatible /embeddings endpoint: Yandex AI
    Studio, vLLM, a text-embeddings-inference server.

    Every text goes in a request of its own, the way Yandex takes them. Models
    trained for asymmetric search have one model for the documents and one
    for the queries; Yandex names them ...-doc and ...-query.
    """

    semantic = True

    def __init__(
        self,
        model: str,
        base_url: str,
        *,
        query_model: str = "",
        api_key: str | None = None,
        project: str = "",
        dimensions: int | None = None,
        duplicate_threshold: float = 0.88,
        search_floor: float = 0.0,
        requests_per_second: float = 8.0,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        width = f"@{dimensions}" if dimensions else ""
        self.model_id = f"openai:{short_model_name(model)}{width}"
        self.duplicate_threshold = duplicate_threshold
        self.search_floor = search_floor
        self._models: dict[Kind, str] = {"document": model, "query": query_model or model}
        self._url = f"{base_url.rstrip('/')}/embeddings"
        self._headers = {
            **({"Authorization": f"Bearer {api_key}"} if api_key else {}),
            **({"OpenAI-Project": project} if project else {}),
        }
        self._dimensions = dimensions
        self._pace = _Pace(requests_per_second)
        self._timeout = timeout
        self._transport = transport
        # Requests sent, 429s included: what the provider bills and limits.
        self.requests = 0

    async def embed(self, texts: list[str], kind: Kind) -> list[list[float]]:
        if not texts:
            return []
        slots = asyncio.Semaphore(OPENAI_EMBED_IN_FLIGHT)
        # A client per call: it holds connections of the loop it was made in.
        async with httpx.AsyncClient(
            headers=self._headers, timeout=self._timeout, transport=self._transport
        ) as client:

            async def one(text: str) -> list[float]:
                async with slots:
                    return await self._embed_one(client, text, kind)

            return list(await asyncio.gather(*(one(text) for text in texts)))

    async def _embed_one(self, client: httpx.AsyncClient, text: str, kind: Kind) -> list[float]:
        body: dict[str, object] = {
            "model": self._models[kind],
            "input": text[:OPENAI_EMBED_MAX_CHARS],
        }
        if self._dimensions:
            body["dimensions"] = self._dimensions
        for attempt in range(OPENAI_EMBED_RETRIES + 1):
            await asyncio.sleep(self._pace.delay())
            self.requests += 1
            response = await client.post(self._url, json=body)
            # A full quota is a queue, not a failure: the request waits and goes
            # again, spread out so that refused requests do not return together.
            if response.status_code == 429 and attempt < OPENAI_EMBED_RETRIES:
                step = min(OPENAI_EMBED_PAUSE_SECONDS * 2**attempt, OPENAI_EMBED_MAX_PAUSE_SECONDS)
                await asyncio.sleep(step * random.uniform(0.5, 1.5))  # noqa: S311
                continue
            response.raise_for_status()
            vector: list[float] = response.json()["data"][0]["embedding"]
            return fit_dimension(vector)
        raise AssertionError("the last attempt returns or raises")
