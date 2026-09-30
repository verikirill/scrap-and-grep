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
    String,
    Text,
    UniqueConstraint,
    func,
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


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid7)
    name: Mapped[str] = mapped_column(String(120))
    spec: Mapped[dict[str, Any]] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Digest(Base):
    __tablename__ = "digests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid7)
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

    __table_args__ = (Index("ix_digests_profile_created", "profile_id", "created_at"),)


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
