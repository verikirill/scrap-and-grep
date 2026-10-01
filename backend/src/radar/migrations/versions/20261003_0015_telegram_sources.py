"""public Telegram channels as sources

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-03 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="rss"),
    )
    op.add_column("sources", sa.Column("last_post_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("sources", "last_post_id")
    op.drop_column("sources", "kind")
