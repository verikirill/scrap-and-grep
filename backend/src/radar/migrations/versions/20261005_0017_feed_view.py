"""the look of the feed, chosen by the reader

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-05 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("feed_view", sa.String(length=16), nullable=False, server_default="cards"),
    )


def downgrade() -> None:
    op.drop_column("users", "feed_view")
