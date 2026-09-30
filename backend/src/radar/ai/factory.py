"""Build the configured providers."""

from dataclasses import dataclass
from functools import lru_cache

from radar.ai.embedder import Embedder, HashingEmbedder, OllamaEmbedder
from radar.ai.heuristic import HeuristicIntelligence
from radar.ai.intelligence import Intelligence
from radar.ai.resilient import CachedIntelligence, CircuitBreaker, ResilientIntelligence
from radar.cache import get_cache
from radar.config import EMBEDDING_DIM, get_settings


@dataclass(frozen=True, slots=True)
class EmbeddingPreset:
    """How a model family expects its input, taken from the model cards."""

    query_prefix: str = ""
    document_prefix: str = ""
    # Ask the server for a shorter Matryoshka vector instead of truncating here.
    dimensions: int | None = None


# Ollama does not add prompts itself; a model used without its prefix loses
# retrieval quality silently. Matched by the start of the model tag.
_EMBEDDING_PRESETS: dict[str, EmbeddingPreset] = {
    "qwen3-embedding": EmbeddingPreset(
        query_prefix=(
            "Instruct: Given a topic of interest, retrieve news articles about this topic\nQuery:"
        ),
        dimensions=EMBEDDING_DIM,
    ),
    "embeddinggemma": EmbeddingPreset(
        query_prefix="task: search result | query: ", document_prefix="title: none | text: "
    ),
    "snowflake-arctic-embed2": EmbeddingPreset(query_prefix="query: "),
    "nomic-embed-text": EmbeddingPreset(
        query_prefix="search_query: ", document_prefix="search_document: "
    ),
}


def embedding_preset(model: str) -> EmbeddingPreset:
    return next(
        (preset for name, preset in _EMBEDDING_PRESETS.items() if model.startswith(name)),
        EmbeddingPreset(),
    )


@lru_cache
def get_embedder() -> Embedder:
    settings = get_settings()
    if settings.embedding_provider == "ollama":
        preset = embedding_preset(settings.embedding_model)
        return OllamaEmbedder(
            settings.embedding_model,
            settings.ollama_base_url,
            query_prefix=settings.embedding_query_prefix or preset.query_prefix,
            document_prefix=settings.embedding_document_prefix or preset.document_prefix,
            dimensions=preset.dimensions,
            keep_alive=settings.ollama_keep_alive_seconds,
            batch_size=settings.embedding_batch_size,
        )
    return HashingEmbedder()


@lru_cache
def get_intelligence() -> Intelligence:
    settings = get_settings()
    fallback = HeuristicIntelligence()
    if settings.llm_provider != "ollama":
        return fallback

    from radar.ai.ollama import OllamaIntelligence

    primary = OllamaIntelligence(
        settings.llm_model,
        settings.ollama_base_url,
        temperature=settings.llm_temperature,
        num_ctx=settings.llm_num_ctx,
        keep_alive=settings.ollama_keep_alive_seconds,
        concurrency=settings.llm_concurrency,
        timeout=settings.llm_timeout_seconds,
    )
    breaker = CircuitBreaker(settings.breaker_failure_threshold, settings.breaker_reset_seconds)
    return CachedIntelligence(ResilientIntelligence(primary, fallback, breaker), get_cache())
