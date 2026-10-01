"""ORM models. The schema itself is owned by Alembic migrations."""

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from radar.config import EMBEDDING_DIM
from radar.db.base import Base

# The "russian" configuration stems Cyrillic words with the Russian Snowball
# stemmer and ASCII words with the English one, so a single column serves both
# languages.
_SEARCH_EXPR = (
    "setweight(to_tsvector('russian', coalesce(title, '')), 'A') || "
    "setweight(to_tsvector('russian', coalesce(summary, '')), 'B') || "
    "setweight(to_tsvector('russian', left(coalesce(content, ''), 20000)), 'C')"
)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    feed_url: Mapped[str] = mapped_column(Text, unique=True)
    site_url: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(32))
    language: Mapped[str] = mapped_column(String(8), default="ru")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    fetch_full_text: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    etag: Mapped[str | None] = mapped_column(Text)
    last_modified: Mapped[str | None] = mapped_column(Text)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String(32))
    last_error: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(Text, unique=True)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(300))
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    language: Mapped[str] = mapped_column(String(8))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    content_hash: Mapped[str] = mapped_column(String(64))
    # The story's picture: its address, a stored copy (radar.images.store) when
    # the address alone did not do, and when the page was last asked for one.
    image_url: Mapped[str | None] = mapped_column(Text)
    image_key: Mapped[str | None] = mapped_column(String(64))
    image_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Words of the full text, for the reading time; None while only a teaser is known.
    word_count: Mapped[int | None] = mapped_column(Integer)
    # When the page was last read to count them, so it is not read again soon.
    measured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    search_tsv: Mapped[Any] = mapped_column(TSVECTOR, Computed(_SEARCH_EXPR, persisted=True))

    source: Mapped[Source] = relationship(lazy="joined")

    __table_args__ = (
        Index("ix_articles_published_at", "published_at"),
        Index("ix_articles_source_published", "source_id", "published_at"),
        Index("ix_articles_content_hash", "content_hash"),
        Index("ix_articles_search_tsv", "search_tsv", postgresql_using="gin"),
    )


class ArticleEmbedding(Base):
    """One vector per (article, model); switching models keeps older vectors."""

    __tablename__ = "article_embeddings"

    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True
    )
    model: Mapped[str] = mapped_column(String(120), primary_key=True)
    embedding: Mapped[Any] = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index(
            "ix_article_embeddings_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid7)
    # Stored lowercased; the unique index is what makes registration race-free.
    email: Mapped[str] = mapped_column(String(254), unique=True)
    # NULL for the demo account: it has no password and cannot be signed in to
    # with one.
    password_hash: Mapped[str | None] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(String(80))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApiKey(Base):
    """A reader's key for the MCP server. Only a hash of the key is stored;
    the first characters stay readable so the owner can tell keys apart."""

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    prefix: Mapped[str] = mapped_column(String(16))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_api_keys_user", "user_id"),)


class UserSession(Base):
    """A signed-in browser. Only a hash of the cookie value is stored."""

    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_sessions_user", "user_id"),
        Index("ix_sessions_expires", "expires_at"),
    )


class Resume(Base):
    """What was learned from a reader's resume. One per user.

    The uploaded file lives in `payload` only until it is parsed; after that
    the row keeps the extracted facts and nothing of the original text.
    """

    __tablename__ = "resumes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(16), default="processing")
    error: Mapped[str | None] = mapped_column(Text)
    file_format: Mapped[str] = mapped_column(String(16))
    size_bytes: Mapped[int] = mapped_column(Integer)
    # Deferred: the file is read only by the worker that parses it, never
    # by the status polls.
    payload: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    parser: Mapped[str | None] = mapped_column(String(32))
    facts: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    suggestion: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Interaction(Base):
    """One reader signal about one article: a like, a save, an opened link."""

    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16))
    # Where the signal came from: the personal feed or a digest.
    context: Mapped[str] = mapped_column(String(16), default="feed", server_default="feed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "article_id", "kind", name="uq_interactions_user_article_kind"),
        # A like and a dislike of one article cannot both exist, even when
        # two requests race.
        Index(
            "uq_interactions_verdict",
            "user_id",
            "article_id",
            unique=True,
            postgresql_where=text("kind IN ('like', 'dislike')"),
        ),
        Index("ix_interactions_user_created", "user_id", "created_at"),
        Index("ix_interactions_article", "article_id"),
    )


class UserVector(Base):
    """A reader's taste as one vector per embedding model, for finding readers alike."""

    __tablename__ = "user_vectors"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    model: Mapped[str] = mapped_column(String(120), primary_key=True)
    embedding: Mapped[Any] = mapped_column(Vector(EMBEDDING_DIM))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    spec: Mapped[dict[str, Any]] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    # How the profile looks in lists: names from the app's icon and colour sets.
    # Not part of the spec, so a new icon is not a new version of the profile.
    icon: Mapped[str | None] = mapped_column(String(24))
    color: Mapped[str | None] = mapped_column(String(12))
    # A link that hands a copy of the profile to another reader; null while
    # the owner shares nothing. Owners see it again, so it is kept as is.
    share_token: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_profiles_user_created", "user_id", "created_at"),
        Index("ux_profiles_share_token", "share_token", unique=True),
    )


class Digest(Base):
    __tablename__ = "digests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL")
    )
    # Snapshot of the interests at generation time: a digest must stay
    # explainable after the profile is edited.
    profile_spec: Mapped[dict[str, Any]] = mapped_column(JSONB)
    profile_version: Mapped[int] = mapped_column(Integer, default=1)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="queued")
    stage: Mapped[str | None] = mapped_column(String(32))
    progress: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    error: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    highlights: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Last sign of life from the build; lets a reaper tell slow from dead.
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    topics: Mapped[list[DigestTopic]] = relationship(
        back_populates="digest", cascade="all, delete-orphan", order_by="DigestTopic.position"
    )
    items: Mapped[list[DigestItem]] = relationship(
        back_populates="digest", cascade="all, delete-orphan", order_by="DigestItem.position"
    )

    __table_args__ = (
        Index("ix_digests_profile_created", "profile_id", "created_at"),
        Index("ix_digests_user_created", "user_id", "created_at"),
    )


class DigestTopic(Base):
    __tablename__ = "digest_topics"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    digest_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("digests.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text)
    overview: Mapped[str] = mapped_column(Text, default="")

    digest: Mapped[Digest] = relationship(back_populates="topics")

    __table_args__ = (Index("ix_digest_topics_digest", "digest_id"),)


class DigestItem(Base):
    """Every graded candidate, selected or not, so the selection is auditable."""

    __tablename__ = "digest_items"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    digest_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("digests.id", ondelete="CASCADE"))
    topic_id: Mapped[int | None] = mapped_column(
        ForeignKey("digest_topics.id", ondelete="SET NULL")
    )
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    selected: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[float] = mapped_column(Float)
    retrieval_score: Mapped[float] = mapped_column(Float, default=0.0)
    # Part of `score` that came from the reader's likes and rejections.
    personal: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    personal_note: Mapped[str] = mapped_column(Text, default="", server_default="")
    relevance: Mapped[int] = mapped_column(Integer, default=0)
    interest_id: Mapped[str | None] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(Text, default="")
    reject_reason: Mapped[str | None] = mapped_column(String(64))
    headline: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    why: Mapped[str] = mapped_column(Text, default="")
    duplicates: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )

    digest: Mapped[Digest] = relationship(back_populates="items")
    article: Mapped[Article] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint("digest_id", "article_id", name="uq_digest_items_digest_article"),
        Index("ix_digest_items_digest", "digest_id", "selected"),
        Index("ix_digest_items_article", "article_id"),
    )


class Video(Base):
    """The short video of a digest. One per digest: making it again replaces it.

    The MP4 itself lives in the media directory under the row id; the row keeps
    the script and the timeline it was rendered from.
    """

    __tablename__ = "videos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid7)
    digest_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("digests.id", ondelete="CASCADE"), unique=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16), default="queued")
    stage: Mapped[str | None] = mapped_column(String(16))
    progress: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    error: Mapped[str | None] = mapped_column(Text)
    script: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # "qwen3-tts:<speaker>" or NULL for a silent video with captions only.
    voice: Mapped[str | None] = mapped_column(String(80))
    # The voice the reader picked; NULL is the voice service's default.
    requested_voice: Mapped[str | None] = mapped_column(String(40))
    # False when the offline writer produced the script.
    by_model: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_videos_user_created", "user_id", "created_at"),
        Index("ix_videos_status", "status"),
        # One video in the works per reader, however many requests race.
        Index(
            "uq_videos_user_active",
            "user_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
    )


class TelegramBot(Base):
    """A bot a reader connected by its token, to post to their channels."""

    __tablename__ = "tg_bots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    telegram_id: Mapped[int] = mapped_column(BigInteger)
    username: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(128))
    # Fernet ciphertext; see radar.publishing.secrets.
    token_encrypted: Mapped[str] = mapped_column(Text)
    token_hint: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="ok", server_default="ok")
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("user_id", "telegram_id", name="uq_tg_bots_user_bot"),)


class TelegramChannel(Base):
    """A channel or group a bot posts to, with what, how and when (settings)."""

    __tablename__ = "tg_channels"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    bot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tg_bots.id", ondelete="CASCADE"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    username: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(256))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # The audience: whose interests pick the news. NULL pauses the news posts.
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL")
    )
    # radar.publishing.settings.ChannelSettings as JSON.
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    status: Mapped[str] = mapped_column(String(16), default="ok", server_default="ok")
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    bot: Mapped[TelegramBot] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint("user_id", "chat_id", name="uq_tg_channels_user_chat"),
        Index("ix_tg_channels_enabled", "enabled"),
    )


class TelegramPost(Base):
    """One post of a channel, from the moment its slot is planned to the
    message in Telegram.

    Statuses: composing (being written), draft (waits for approval), queued
    (approved, waits for its slot), sending, sent, failed, skipped (nothing
    fit the slot).
    """

    __tablename__ = "tg_posts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid7)
    channel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tg_channels.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16), default="news")
    status: Mapped[str] = mapped_column(String(16), default="composing")
    # The slot it fills; NULL for a post made by hand outside the schedule.
    slot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Not sent before this moment: Telegram asked to wait, or a human chose a time.
    not_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    article_ids: Mapped[list[int]] = mapped_column(
        ARRAY(BigInteger), default=list, server_default="{}"
    )
    # radar.publishing.content.PostContent as JSON.
    content: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    by_model: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Queue it once written, or keep it as a draft for a human to approve.
    publish_when_ready: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    message_id: Mapped[int | None] = mapped_column(BigInteger)
    message_url: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # The planner runs every minute and may see one slot many times.
        Index(
            "uq_tg_posts_slot",
            "channel_id",
            "kind",
            "slot_at",
            unique=True,
            postgresql_where=text("slot_at IS NOT NULL"),
        ),
        Index("ix_tg_posts_status_slot", "status", "slot_at"),
        Index("ix_tg_posts_channel_created", "channel_id", "created_at"),
        Index("ix_tg_posts_articles", "article_ids", postgresql_using="gin"),
    )
