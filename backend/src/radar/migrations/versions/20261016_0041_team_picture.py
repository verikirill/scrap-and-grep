"""a team's own picture

Revision ID: 0041
Revises: 0040
Create Date: 2026-10-16 23:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0041"
down_revision: str | None = "0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("teams", sa.Column("picture", sa.LargeBinary(), nullable=True))
    op.add_column(
        "teams", sa.Column("picture_updated_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("teams", "picture_updated_at")
    op.drop_column("teams", "picture")
