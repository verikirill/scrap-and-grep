"""profiles that follow their reader: impressions, learned interests, suggestions

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-02 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 1024


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("adaptive", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column("profiles", sa.Column("adapt_since", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "impressions",
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "article_id",
            sa.BigInteger(),
            sa.ForeignKey("articles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("context", sa.String(length=16), primary_key=True),
        sa.Column("times", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_impressions_user_seen", "impressions", ["user_id", "last_seen_at"])

    op.create_table(
        "interest_adaptations",
        sa.Column(
            "profile_id",
            sa.UUID(),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("interest_id", sa.String(length=64), primary_key=True),
        sa.Column("model", sa.String(length=120), primary_key=True),
        sa.Column("base_hash", sa.String(length=64), nullable=False),
        sa.Column("factor", sa.Float(), nullable=False, server_default="1"),
        sa.Column("vector", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("drift", sa.Float(), nullable=False, server_default="0"),
        sa.Column("positives", sa.Float(), nullable=False, server_default="0"),
        sa.Column("negatives", sa.Float(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "profile_suggestions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.UUID(),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("keywords", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column(
            "article_ids", postgresql.ARRAY(sa.BigInteger()), nullable=False, server_default="{}"
        ),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_profile_suggestions_profile", "profile_suggestions", ["profile_id", "status"]
    )


def downgrade() -> None:
    op.drop_index("ix_profile_suggestions_profile", table_name="profile_suggestions")
    op.drop_table("profile_suggestions")
    op.drop_table("interest_adaptations")
    op.drop_index("ix_impressions_user_seen", table_name="impressions")
    op.drop_table("impressions")
    op.drop_column("profiles", "adapt_since")
    op.drop_column("profiles", "adaptive")
