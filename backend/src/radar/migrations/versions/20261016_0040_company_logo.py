"""a company's logo

Revision ID: 0040
Revises: 0039
Create Date: 2026-10-16 22:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0040"
down_revision: str | None = "0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("logo", sa.LargeBinary(), nullable=True))
    op.add_column(
        "companies", sa.Column("logo_updated_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("companies", "logo_updated_at")
    op.drop_column("companies", "logo")
