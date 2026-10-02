"""Build the configured providers."""

from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

from radar.ai.embedder import Embedder, HashingEmbedder, OllamaEmbedder
from radar.ai.heuristic import HeuristicIntelligence
from radar.ai.intelligence import Intelligence
from radar.ai.resilient import CachedIntelligence, CircuitBreaker, ResilientIntelligence
from radar.cache import get_cache
from radar.config import EMBEDDING_DIM, get_settings

if TYPE_CHECKING:
    from radar.ai.ollama import OllamaChat


@dataclass(frozen=True, slots=True)
class EmbeddingPreset:
    """How a model family expects its input, taken from the model cards."""

    query_prefix: str = ""
    document_prefix: str = ""
    # Ask the server for a shorter Matryoshka vector instead of truncating here.
    dimensions: int | None = None
    # Cosine above which two articles are one story. Model-specific: each model
    # spreads similarities over its own range. 0.88 is a cautious default for
    # models that were not calibrated on real data.
    duplicate_threshold: float = 0.88
    # Cosine a search query needs to find an article by meaning. 0 leaves only
    # the z-score rule, for models nobody calibrated.
    search_floor: float = 0.0


# Ollama does not add prompts itself; a model used without its prefix loses
# retrieval quality silently. Matched by the start of the model tag.
_EMBEDDING_PRESETS: dict[str, EmbeddingPreset] = {
    "qwen3-embedding": EmbeddingPreset(
        query_prefix=(
            "Instruct: Given a topic of interest, retrieve news articles about this topic\nQuery:"
        ),
        dimensions=EMBEDDING_DIM,
    ),
    # Calibrated on a real digest: four reports on one Citrix incident sit at
    # 0.73-0.84 to each other, the closest unrelated pair at 0.68. Search on
    # ten queries over 2 357 articles: relevant matches by meaning from 0.38,
    # noise ("цифровая подстанция МЭК 61850" with no article on it) at 0.31.
    "embeddinggemma": EmbeddingPreset(
        query_prefix="task: search result | query: ",
        document_prefix="title: none | text: ",
        duplicate_threshold=0.76,
        search_floor=0.38,
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
            duplicate_threshold=preset.duplicate_threshold,
            search_floor=preset.search_floor,
            keep_alive=settings.ollama_keep_alive_seconds,
            batch_size=settings.embedding_batch_size,
        )
    return HashingEmbedder()


@lru_cache
def get_chat(temperature: float | None = None) -> OllamaChat | None:
    """The model connection, or None in offline mode. Writing that must vary
    between calls passes its own temperature."""
    settings = get_settings()
    if settings.llm_provider != "ollama":
        return None

    from radar.ai.ollama import OllamaChat

    return OllamaChat(
        settings.llm_model,
        settings.llm_base_url or settings.ollama_base_url,
        api_key=settings.llm_api_key.get_secret_value() if settings.llm_api_key else None,
        reasoning=settings.llm_reasoning,
        temperature=settings.llm_temperature if temperature is None else temperature,
        num_ctx=settings.llm_num_ctx,
        keep_alive=settings.ollama_keep_alive_seconds,
        concurrency=settings.llm_concurrency,
        timeout=settings.llm_timeout_seconds,
    )


@lru_cache
def get_breaker() -> CircuitBreaker:
    """One breaker per process: every step that calls the model shares the
    knowledge that it is down."""
    settings = get_settings()
    return CircuitBreaker(settings.breaker_failure_threshold, settings.breaker_reset_seconds)


@lru_cache
def get_intelligence() -> Intelligence:
    fallback = HeuristicIntelligence()
    chat = get_chat()
    if chat is None:
        return fallback

    from radar.ai.ollama import OllamaIntelligence

    primary = OllamaIntelligence(chat)
    return CachedIntelligence(ResilientIntelligence(primary, fallback, get_breaker()), get_cache())
