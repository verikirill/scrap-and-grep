"""sources without a feed: a news page and the CSS selector of its links

Revision ID: 0025
Revises: 0024
Create Date: 2026-10-11 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("link_selector", sa.Text()))


def downgrade() -> None:
    op.drop_column("sources", "link_selector")
