"""articles translated for the reader

Revision ID: 0033
Revises: 0032
Create Date: 2026-10-15 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "article_translations",
        sa.Column(
            "article_id",
            sa.BigInteger(),
            sa.ForeignKey("articles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("source_language", sa.String(length=8), nullable=False),
        sa.Column("fingerprint", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("blocks", postgresql.JSONB(), nullable=False),
        sa.Column("kept_original", sa.Integer(), server_default="0", nullable=False),
        sa.Column("translated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("article_id", "language"),
    )


def downgrade() -> None:
    op.drop_table("article_translations")
