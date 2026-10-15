"""when a reader finished the first-run introduction

Revision ID: 0036
Revises: 0035
Create Date: 2026-10-15 20:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("onboarded_at", sa.DateTime(timezone=True), nullable=True))
    # Readers who were here before the introduction existed already know the
    # service: only accounts registered from now on are offered it.
    op.execute("UPDATE users SET onboarded_at = created_at")


def downgrade() -> None:
    op.drop_column("users", "onboarded_at")
