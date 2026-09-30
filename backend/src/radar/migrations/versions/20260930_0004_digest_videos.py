"""short videos of digests

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-30 23:40:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "videos",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("digest_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("stage", sa.String(length=16), nullable=True),
        sa.Column("progress", sa.Float(), server_default="0", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("script", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("voice", sa.String(length=80), nullable=True),
        sa.Column("by_model", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["digest_id"], ["digests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("digest_id"),
    )
    op.create_index("ix_videos_user_created", "videos", ["user_id", "created_at"])
    op.create_index("ix_videos_status", "videos", ["status"])
    # One video in the works per reader, however many requests race.
    op.create_index(
        "uq_videos_user_active",
        "videos",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )


def downgrade() -> None:
    op.drop_index("uq_videos_user_active", table_name="videos")
    op.drop_index("ix_videos_status", table_name="videos")
    op.drop_index("ix_videos_user_created", table_name="videos")
    op.drop_table("videos")
