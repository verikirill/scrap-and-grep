"""what a management digest's period means for the company

Revision ID: 0026
Revises: 0025
Create Date: 2026-10-12 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "digests",
        sa.Column("implications", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("digests", "implications")
