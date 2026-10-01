"""pictures of articles: the address, a stored copy, the last page check

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-01 15:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("image_url", sa.Text(), nullable=True))
    op.add_column("articles", sa.Column("image_key", sa.String(length=64), nullable=True))
    op.add_column(
        "articles", sa.Column("image_checked_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("articles", "image_checked_at")
    op.drop_column("articles", "image_key")
    op.drop_column("articles", "image_url")
