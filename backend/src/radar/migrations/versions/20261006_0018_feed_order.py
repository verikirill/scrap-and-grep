"""the order the feed opens in, chosen by the reader

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-06 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("feed_order", sa.String(length=8), nullable=False, server_default="new"),
    )


def downgrade() -> None:
    op.drop_column("users", "feed_order")
