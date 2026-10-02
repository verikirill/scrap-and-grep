"""a proxy of each source's own, and whether a proxy read it last

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-10 13:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("proxy_url", sa.Text()))
    op.add_column(
        "sources",
        sa.Column("fetch_via_proxy", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("sources", "fetch_via_proxy")
    op.drop_column("sources", "proxy_url")
