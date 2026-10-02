"""how each source is read: the step of the fetch ladder that worked

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-10 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("fetch_method", sa.String(16)))
    op.add_column("sources", sa.Column("fetch_note", sa.Text()))
    op.add_column("sources", sa.Column("fetch_changed_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("sources", "fetch_changed_at")
    op.drop_column("sources", "fetch_note")
    op.drop_column("sources", "fetch_method")
