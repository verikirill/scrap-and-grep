"""Runtime configuration, read once from the environment."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Every stored vector has this width. Smaller models are zero-padded (cosine
# similarity is unchanged), larger ones are truncated and re-normalised.
EMBEDDING_DIM = 1024


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="RADAR_", extra="ignore")

    environment: Literal["local", "test", "production"] = "local"
    log_level: str = "INFO"
    log_json: bool = True

    # PostgreSQL. `database_url` may point at PgBouncer; the LangGraph
    # checkpointer keeps its own pool and can bypass the bouncer.
    database_url: str = "postgresql+psycopg://radar:radar@127.0.0.1:5432/radar"
    checkpoint_database_url: str | None = None
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_disable_prepared_statements: bool = False

    # Valkey / Redis. Broker and cache live in separate logical databases so
    # that cache eviction never touches queued tasks.
    broker_url: str = "redis://127.0.0.1:6379/0"
    cache_url: str = "redis://127.0.0.1:6379/1"

    # AI providers. "hashing" and "heuristic" are the offline stand-ins that
    # keep the pipeline working when no model server is reachable.
    embedding_provider: Literal["hashing", "ollama"] = "hashing"
    embedding_model: str = "bge-m3"
    embedding_query_prefix: str = ""
    embedding_document_prefix: str = ""
    embedding_batch_size: int = 32
    llm_provider: Literal["heuristic", "ollama"] = "heuristic"
    llm_model: str = "qwen3:8b"
    llm_temperature: float = 0.1
    llm_num_ctx: int = 8192
    llm_timeout_seconds: float = 120.0
    llm_concurrency: int = 4
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_keep_alive: str = "30m"
    breaker_failure_threshold: int = 3
    breaker_reset_seconds: float = 30.0

    # Ingestion
    ingest_cron: str = "*/15 * * * *"
    http_timeout_seconds: float = 20.0
    http_user_agent: str = "RadarDigestBot/0.1 (+hackathon prototype)"
    fulltext_concurrency: int = 4
    max_feed_bytes: int = 8_000_000
    allow_private_feed_hosts: bool = False

    # Selection defaults
    candidate_limit: int = 80
    per_interest_limit: int = 40

    # API
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    rate_limit_per_minute: int = 120
    digest_rate_limit_per_minute: int = 10
    seed_on_start: bool = True

    @computed_field  # type: ignore[prop-decorator]
    @property
    def checkpoint_dsn(self) -> str:
        """libpq-style DSN for psycopg (LangGraph does not speak SQLAlchemy URLs)."""
        url = self.checkpoint_database_url or self.database_url
        return url.replace("postgresql+psycopg://", "postgresql://", 1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
