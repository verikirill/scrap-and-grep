"""a link that hands a copy of a profile to another reader

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-01 23:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("share_token", sa.String(length=32), nullable=True))
    op.create_index("ux_profiles_share_token", "profiles", ["share_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ux_profiles_share_token", table_name="profiles")
    op.drop_column("profiles", "share_token")
