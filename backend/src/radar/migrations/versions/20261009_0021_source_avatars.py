"""the picture of each source

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-09 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("avatar_checked_at", sa.DateTime(timezone=True)))
    op.add_column("sources", sa.Column("avatar_updated_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("sources", "avatar_updated_at")
    op.drop_column("sources", "avatar_checked_at")
