"""a ready picture for a reader without a photo

Revision ID: 0037
Revises: 0036
Create Date: 2026-10-15 22:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Left empty for existing accounts: the API derives a stable picture from
    # the account id until the reader picks one.
    op.add_column("users", sa.Column("avatar_preset", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_preset")
