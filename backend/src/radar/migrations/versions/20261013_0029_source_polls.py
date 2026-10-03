"""every poll of a source for a week: how the sources are doing

Revision ID: 0029
Revises: 0028
Create Date: 2026-10-13 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_polls",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "source_id",
            sa.Integer(),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "polled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("error_kind", sa.String(16)),
        sa.Column("new_articles", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index("ix_source_polls_polled_at", "source_polls", ["polled_at"])
    op.create_index("ix_source_polls_source_polled", "source_polls", ["source_id", "polled_at"])


def downgrade() -> None:
    op.drop_index("ix_source_polls_source_polled", table_name="source_polls")
    op.drop_index("ix_source_polls_polled_at", table_name="source_polls")
    op.drop_table("source_polls")
