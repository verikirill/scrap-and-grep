"""Build the configured providers."""

from functools import lru_cache

from radar.ai.embedder import Embedder, HashingEmbedder, OllamaEmbedder
from radar.ai.heuristic import HeuristicIntelligence
from radar.ai.intelligence import Intelligence
from radar.ai.resilient import CachedIntelligence, CircuitBreaker, ResilientIntelligence
from radar.cache import get_cache
from radar.config import get_settings


@lru_cache
def get_embedder() -> Embedder:
    settings = get_settings()
    if settings.embedding_provider == "ollama":
        return OllamaEmbedder(
            settings.embedding_model,
            settings.ollama_base_url,
            query_prefix=settings.embedding_query_prefix,
            document_prefix=settings.embedding_document_prefix,
            keep_alive=settings.ollama_keep_alive,
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
        keep_alive=settings.ollama_keep_alive,
        concurrency=settings.llm_concurrency,
        timeout=settings.llm_timeout_seconds,
    )
    breaker = CircuitBreaker(settings.breaker_failure_threshold, settings.breaker_reset_seconds)
    return CachedIntelligence(ResilientIntelligence(primary, fallback, breaker), get_cache())
