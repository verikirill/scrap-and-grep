"""deleted readers whose events must go, learned feed rankers

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-02 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "forgotten_readers",
        sa.Column("user_id", sa.UUID(), primary_key=True),
        sa.Column(
            "deleted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "ranker_models",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("version", sa.String(length=40), nullable=False, unique=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("trained_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trained_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lists", sa.Integer(), nullable=False),
        sa.Column("rows", sa.Integer(), nullable=False),
        sa.Column("metrics", JSONB(), nullable=False),
        sa.Column("features", JSONB(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "uq_ranker_models_active",
        "ranker_models",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index("ix_ranker_models_created", "ranker_models", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_ranker_models_created", table_name="ranker_models")
    op.drop_index("uq_ranker_models_active", table_name="ranker_models")
    op.drop_table("ranker_models")
    op.drop_table("forgotten_readers")
