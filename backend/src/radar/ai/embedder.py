"""Text embedders behind one interface.

`HashingEmbedder` is the offline stand-in: a deterministic bag of character
n-grams. It knows nothing about meaning, but inflected forms of a word share
most of their n-grams, which is enough to rank Russian and English text by
lexical closeness without any model server.
"""

import math
import zlib
from typing import Literal, Protocol

import numpy as np

from radar.config import EMBEDDING_DIM
from radar.text import content_tokens

Kind = Literal["query", "document"]


class Embedder(Protocol):
    model_id: str
    # Cosine similarity above which two articles are treated as the same story.
    duplicate_threshold: float
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
        keep_alive: int = 1800,
        batch_size: int = 32,
    ) -> None:
        from langchain_ollama import OllamaEmbeddings

        self.model_id = f"ollama:{model}"
        self.duplicate_threshold = duplicate_threshold
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
