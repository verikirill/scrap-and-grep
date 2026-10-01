"""the voice a reader picked for a short video

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-01 02:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("videos", sa.Column("requested_voice", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("videos", "requested_voice")
