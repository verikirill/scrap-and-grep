"""the kind, priority and card of a digest entry; the links of a Telegram post

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-07 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "digest_items",
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="news"),
    )
    op.add_column("digest_items", sa.Column("priority", sa.String(length=8), nullable=True))
    op.add_column(
        "digest_items",
        sa.Column(
            "card", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"
        ),
    )
    op.add_column(
        "articles",
        sa.Column(
            "links", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"
        ),
    )


def downgrade() -> None:
    op.drop_column("articles", "links")
    op.drop_column("digest_items", "card")
    op.drop_column("digest_items", "priority")
    op.drop_column("digest_items", "kind")
