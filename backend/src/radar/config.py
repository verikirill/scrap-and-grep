"""Runtime configuration, read once from the environment."""

from functools import lru_cache
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Every stored vector has this width. Smaller models are zero-padded (cosine
# similarity is unchanged), larger ones are truncated and re-normalised.
EMBEDDING_DIM = 1024
PROXY_SCHEMES = frozenset({"http", "https", "socks5", "socks5h"})


def check_proxy_url(url: str) -> str:
    """A proxy address as httpx and curl take it, or ValueError."""
    parts = urlsplit(url)
    if parts.scheme not in PROXY_SCHEMES or not parts.hostname or parts.path not in {"", "/"}:
        raise ValueError("a proxy is scheme://[user:password@]host:port: http, https or socks5")
    return url


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
    # "openai" is any OpenAI-compatible Chat Completions server: Yandex AI
    # Studio, vLLM, Ollama's /v1. Its base URL is required.
    llm_provider: Literal["heuristic", "ollama", "openai"] = "heuristic"
    # Qwen3.6 35B-A3B, one of the models of the finals, run locally: closed
    # external APIs are forbidden there. 22.6 GB in Q4_K_M; on a card of
    # 12-16 GB Ollama runs the layers that do not fit on the CPU. See .env.example.
    llm_model: str = "qwen3.6:35b-a3b"
    # Where the language model is asked. Empty means the Ollama below, the one
    # that also makes the embeddings. Ollama's cloud is for development only.
    llm_base_url: str = ""
    llm_api_key: SecretStr | None = None
    # Yandex AI Studio wants the folder id as the OpenAI project.
    llm_project: str = ""
    # Hidden reasoning before the answer. Qwen answers a schema as well
    # without it; gpt-oss cannot switch it off and takes a level.
    llm_reasoning: Literal["off", "low", "medium", "high"] = "off"
    # Zero: a grade must not drift between two builds of the same week, or an
    # edit of the interests is lost among changes nobody made.
    llm_temperature: float = 0.0
    llm_num_ctx: int = 8192
    llm_timeout_seconds: float = 120.0
    # Requests in flight at once. One local GPU serves them one after another
    # (see DECISIONS.md), 2 keeps it busy; a server with several cards or the
    # cloud takes more.
    llm_concurrency: int = 2
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_keep_alive_seconds: int = 1800
    breaker_failure_threshold: int = 3
    breaker_reset_seconds: float = 30.0

    # The CISA catalogue of exploited vulnerabilities, refreshed every hour
    # (a 304 when unchanged). Empty turns the lookup off; BDU still answers.
    kev_url: str = (
        "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    )
    # MITRE ATT&CK for the techniques of an attack card, refreshed once a day.
    # Empty turns the refresh off; the snapshot in the package still answers.
    attack_url: str = (
        "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/"
        "enterprise-attack/enterprise-attack.json"
    )

    # Ingestion
    ingest_cron: str = "*/15 * * * *"
    http_timeout_seconds: float = 20.0
    http_user_agent: str = "TailGrepBot/0.1 (+hackathon prototype)"
    fulltext_concurrency: int = 4
    max_feed_bytes: int = 8_000_000
    allow_private_feed_hosts: bool = False
    # Sites whose certificates come from the Russian national CA (Минцифры).
    # It is trusted for these hosts and their subdomains only.
    # БДУ АСУ ТП signs in its readers at bdu-ibasu.fstec.ru, also of that CA.
    russian_ca_hosts: list[str] = Field(
        default_factory=lambda: [
            "bdu.fstec.ru",
            "bduasutp.fstec.ru",
            "bdu-ibasu.fstec.ru",
            "ptsecurity.com",
        ]
    )
    # Where public Telegram channels are read (t.me/s/<name>), tried in turn.
    # Where Telegram is blocked, put a mirror of t.me first.
    telegram_preview_urls: list[str] = Field(
        default_factory=lambda: ["https://t.me", "https://telegram.me"], min_length=1
    )

    # Reading sites that refuse a bot (ingest/fetch.py). A page that answers
    # 401/403/429/503 or a challenge is asked again a step up the ladder:
    # browser headers, the TLS fingerprint of Chrome, a headless browser,
    # FlareSolverr.
    # What a browser sends on the second step and later.
    browser_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    )
    # The third step: curl_cffi with the TLS and HTTP/2 fingerprint of Chrome.
    fetch_impersonate: bool = True
    # The stack's headless browser (browser/) for pages drawn by script and
    # challenges that stop curl_cffi: http://browser:8000. Empty turns the
    # step off. A page gets this long, its challenge included.
    browser_url: str = ""
    browser_timeout_seconds: float = Field(default=30.0, ge=5, le=120)
    # FlareSolverr inside the stack (the solver profile) for pages that stop
    # the browser too: http://flaresolverr:8191. Empty turns the step off.
    flaresolverr_url: str = ""
    flaresolverr_timeout_seconds: float = Field(default=60.0, ge=10)
    # An article page whose text is shorter than this is taken for a stub.
    fetch_min_article_chars: int = Field(default=300, ge=0)
    # Politeness: the least pause between two requests to one host, plus up
    # to half of it at random, within one process.
    fetch_host_interval_seconds: float = Field(default=1.0, ge=0)
    # A proxy for every request, the corporate one in a closed network:
    # http://, https:// or socks5://. A source may have its own instead.
    http_proxy: str = ""
    # Proxies tried in turn when a site refuses every step without one
    # (403, 429 or no answer), comma-separated: for geo-blocks and limits.
    http_proxies: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # Longest a digest build may run. A build whose worker died is handed to
    # another worker after this long, and resumes from its last checkpoint.
    digest_task_timeout_seconds: int = Field(default=1200, ge=120)

    # Selection defaults
    candidate_limit: int = 60
    per_interest_limit: int = 40

    # API
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    rate_limit_per_minute: int = 120
    # Pictures of articles opened in the reader, up to 40 a page.
    picture_rate_limit_per_minute: int = 300
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

    # Copies of article pictures, kept when a link is not enough (see
    # radar.images.store): on the media volume, or in any S3-compatible store.
    image_store: Literal["local", "s3"] = "local"
    s3_endpoint: str = "s3:8333"
    s3_bucket: str = "radar-images"
    s3_access_key: str = ""
    s3_secret_key: SecretStr | None = None
    s3_secure: bool = False
    s3_region: str = ""

    # Posting to Telegram channels. Bot tokens are stored encrypted with a key
    # derived from this secret; without it no bot can be added.
    secret_key: SecretStr | None = None
    telegram_api_url: str = "https://api.telegram.org"
    telegram_timeout_seconds: float = Field(default=30.0, ge=5)
    # Posts are written with more freedom than grades: two channels that take
    # the same news must not get the same text.
    publish_temperature: float = Field(default=0.7, ge=0.0, le=1.5)
    publish_rate_limit_per_minute: int = 20
    max_bots_per_user: int = 10
    max_channels_per_user: int = 30

    # The MCP server: calls a minute per key. A search ranks the whole feed.
    mcp_rate_limit_per_minute: int = 60

    # Reader events (what was served, seen, opened, marked) go through a
    # Valkey stream into ClickHouse, for analytics and for training the feed
    # ranker. An empty URL turns events off; nothing else depends on them.
    clickhouse_url: str = ""
    clickhouse_user: str = "default"
    clickhouse_password: SecretStr | None = None
    clickhouse_database: str = "radar"
    # Events waiting for ClickHouse. While it is down they pile up here; past
    # this many the oldest are dropped, so an outage cannot fill Valkey.
    events_queue_max: int = Field(default=200_000, ge=1_000)

    # The learned feed ranker, trained on the events every night. A model is
    # switched on only when it beats the hand blend on days it did not see;
    # then it serves this share of readers (picked by a hash of their id) and
    # the rest stay on the hand blend for comparison. 0 keeps everyone on the
    # hand blend.
    ranker_share: float = Field(default=0.5, ge=0.0, le=1.0)
    ranker_train_cron: str = "30 3 * * *"
    ranker_train_days: int = Field(default=28, ge=4, le=180)

    @field_validator("russian_ca_hosts")
    @classmethod
    def _national_ca_hosts(cls, hosts: list[str]) -> list[str]:
        names = [host.strip().strip(".").lower() for host in hosts]
        for name in names:
            # "ru" alone would hand the whole zone to that CA.
            if "." not in name or not all(name.split(".")):
                raise ValueError(f"not a host name for the national CA: {name!r}")
        return names

    @field_validator("telegram_preview_urls")
    @classmethod
    def _preview_bases(cls, urls: list[str]) -> list[str]:
        for url in urls:
            parts = urlsplit(url)
            if (
                parts.scheme not in {"http", "https"}
                or not parts.hostname
                or parts.username
                or parts.query
                or parts.fragment
            ):
                raise ValueError(f"not a base address for t.me pages: {url!r}")
        return urls

    @field_validator("http_proxies", mode="before")
    @classmethod
    def _proxy_list(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @field_validator("http_proxies")
    @classmethod
    def _proxy_pool(cls, urls: list[str]) -> list[str]:
        for url in urls:
            check_proxy_url(url)
        return urls

    @field_validator("http_proxy")
    @classmethod
    def _one_proxy(cls, url: str) -> str:
        return check_proxy_url(url) if url else url

    @field_validator("llm_api_key", mode="before")
    @classmethod
    def _unset_key(cls, value: object) -> object:
        # Compose passes a key that is not set as an empty string.
        return value or None

    @model_validator(mode="after")
    def _cloud_needs_a_key(self) -> Self:
        # Without the key every answer is a 401, the breaker quietly falls back
        # to the offline mode, and the stack looks fine while no model works.
        cloud = urlsplit(self.llm_base_url).hostname == "ollama.com"
        if self.llm_provider != "heuristic" and cloud and self.llm_api_key is None:
            raise ValueError("RADAR_LLM_API_KEY is required for a model in Ollama's cloud")
        if self.llm_provider == "openai" and not self.llm_base_url:
            raise ValueError("RADAR_LLM_BASE_URL is required for an OpenAI-compatible model")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def checkpoint_dsn(self) -> str:
        """libpq-style DSN for psycopg (LangGraph does not speak SQLAlchemy URLs)."""
        url = self.checkpoint_database_url or self.database_url
        return url.replace("postgresql+psycopg://", "postgresql://", 1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
