"""bots, channels and posts for publishing to Telegram

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-01 14:00:00
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _stamp(name: str) -> sa.Column[datetime]:
    return sa.Column(
        name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "tg_bots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("token_encrypted", sa.Text(), nullable=False),
        sa.Column("token_hint", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="ok", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        _stamp("created_at"),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "telegram_id", name="uq_tg_bots_user_bot"),
    )
    op.create_table(
        "tg_channels",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("bot_id", sa.UUID(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("profile_id", sa.UUID(), nullable=True),
        sa.Column(
            "settings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("status", sa.String(length=16), server_default="ok", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        _stamp("created_at"),
        _stamp("updated_at"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bot_id"], ["tg_bots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "chat_id", name="uq_tg_channels_user_chat"),
    )
    op.create_index("ix_tg_channels_enabled", "tg_channels", ["enabled"])
    op.create_table(
        "tg_posts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("channel_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("slot_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("not_before", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "article_ids",
            postgresql.ARRAY(sa.BigInteger()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("by_model", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("publish_when_ready", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("message_url", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        _stamp("created_at"),
        _stamp("updated_at"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["channel_id"], ["tg_channels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    # The planner runs every minute and may see one slot many times.
    op.create_index(
        "uq_tg_posts_slot",
        "tg_posts",
        ["channel_id", "kind", "slot_at"],
        unique=True,
        postgresql_where=sa.text("slot_at IS NOT NULL"),
    )
    op.create_index("ix_tg_posts_status_slot", "tg_posts", ["status", "slot_at"])
    op.create_index("ix_tg_posts_channel_created", "tg_posts", ["channel_id", "created_at"])
    op.create_index("ix_tg_posts_articles", "tg_posts", ["article_ids"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_table("tg_posts")
    op.drop_index("ix_tg_channels_enabled", table_name="tg_channels")
    op.drop_table("tg_channels")
    op.drop_table("tg_bots")
