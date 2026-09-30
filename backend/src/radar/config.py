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
    # Safe behind PgBouncer in transaction mode; set to false only for a
    # direct connection where server-side prepares are wanted.
    db_disable_prepared_statements: bool = True

    # Valkey / Redis. Broker and cache live in separate logical databases so
    # that cache eviction never touches queued tasks.
    broker_url: str = "redis://127.0.0.1:6379/0"
    cache_url: str = "redis://127.0.0.1:6379/1"

    # AI providers. "hashing" and "heuristic" are the offline stand-ins that
    # keep the pipeline working when no model server is reachable.
    embedding_provider: Literal["hashing", "ollama"] = "hashing"
    embedding_model: str = "embeddinggemma:300m"
    # Empty means "use the preset for the model family" (see ai/factory.py).
    embedding_query_prefix: str = ""
    embedding_document_prefix: str = ""
    embedding_batch_size: int = 32
    llm_provider: Literal["heuristic", "ollama"] = "heuristic"
    llm_model: str = "qwen3.5:9b"
    llm_temperature: float = 0.1
    llm_num_ctx: int = 8192
    llm_timeout_seconds: float = 120.0
    llm_concurrency: int = 2
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_keep_alive_seconds: int = 1800
    breaker_failure_threshold: int = 3
    breaker_reset_seconds: float = 30.0

    # Ingestion
    ingest_cron: str = "*/15 * * * *"
    http_timeout_seconds: float = 20.0
    http_user_agent: str = "RadarDigestBot/0.1 (+hackathon prototype)"
    fulltext_concurrency: int = 4
    max_feed_bytes: int = 8_000_000
    allow_private_feed_hosts: bool = False

    # Longest a digest build may run. A build whose worker died is handed to
    # another worker after this long, and resumes from its last checkpoint.
    digest_task_timeout_seconds: int = Field(default=1200, ge=120)

    # Selection defaults
    candidate_limit: int = 60
    per_interest_limit: int = 40

    # API
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    rate_limit_per_minute: int = 120
    # The preview scans the whole period once per interest; keep it rarer.
    preview_rate_limit_per_minute: int = 40
    # Builds queued or running at once. More would only deepen the model queue.
    max_active_digests: int = 6
    digest_rate_limit_per_minute: int = 10
    seed_on_start: bool = True

    # Accounts. The session cookie is marked Secure only when the stack is
    # served over HTTPS; a plain-HTTP demo on a LAN address would lose it.
    session_ttl_days: int = Field(default=30, ge=1, le=365)
    cookie_secure: bool = False
    registration_open: bool = True
    # "Try without registering": each press creates a throwaway guest account
    # with the example profiles. Handy for a demonstration; turn it off on a
    # server open to the internet.
    demo_login: bool = True
    guest_ttl_hours: int = Field(default=24, ge=1)
    # Sign-in and registration attempts per address and minute.
    auth_rate_limit_per_minute: int = 10

    # Resume parsing. Empty URL means the built-in parser (PDF text layer,
    # DOCX, plain text); a docling service adds layout analysis, OCR and more
    # formats.
    docparser_url: str = ""
    docparser_timeout_seconds: float = 180.0
    resume_max_bytes: int = Field(default=8_000_000, ge=10_000)
    resume_max_pages: int = Field(default=12, ge=1)
    # Characters of resume text handed to the extractor.
    resume_text_limit: int = 12_000
    resume_rate_limit_per_minute: int = 6

    # Personal feed
    feed_window_days: int = Field(default=14, ge=1, le=90)
    feed_cache_seconds: int = 60
    feed_rate_limit_per_minute: int = 60

    # Short videos of digests. An empty renderer URL turns the feature off; an
    # empty voice URL gives silent videos that carry the story in captions.
    shorts_url: str = ""
    shorts_timeout_seconds: float = Field(default=600.0, ge=30)
    tts_url: str = ""
    # Empty means the voice service's own default speaker.
    tts_voice: str = ""
    tts_timeout_seconds: float = Field(default=300.0, ge=10)
    # Finished videos, one MP4 per digest. Shared by the media worker, which
    # writes, and the api, which serves.
    media_dir: str = "data/media"
    shorts_max_items: int = Field(default=4, ge=1, le=6)
    short_rate_limit_per_minute: int = 4
    # Videos queued or being made at once, across all readers: a safety cap,
    # not a schedule. The media worker makes them one after another anyway.
    max_active_shorts: int = 10

    @computed_field  # type: ignore[prop-decorator]
    @property
    def checkpoint_dsn(self) -> str:
        """libpq-style DSN for psycopg (LangGraph does not speak SQLAlchemy URLs)."""
        url = self.checkpoint_database_url or self.database_url
        return url.replace("postgresql+psycopg://", "postgresql://", 1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
