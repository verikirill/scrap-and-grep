"""when a failing source is read next, and what its robots.txt says

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-10 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("retry_at", sa.DateTime(timezone=True)))
    op.add_column("sources", sa.Column("robots_allowed", sa.Boolean()))


def downgrade() -> None:
    op.drop_column("sources", "robots_allowed")
    op.drop_column("sources", "retry_at")
