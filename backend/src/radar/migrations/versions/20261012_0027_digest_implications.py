"""what a management digest means for the company: its own block, before the key points

Revision ID: 0027
Revises: 0026
Create Date: 2026-10-12 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "digests",
        sa.Column("implications", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("digests", "implications")
