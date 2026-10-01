"""readers' pictures, digests built on a schedule

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-02 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_avatars",
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("image", sa.LargeBinary(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.add_column(
        "digests",
        sa.Column("origin", sa.String(length=16), nullable=False, server_default="manual"),
    )
    op.create_table(
        "digest_schedules",
        sa.Column(
            "profile_id",
            sa.UUID(),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("cadence", sa.String(length=16), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=True),
        sa.Column("minute_of_day", sa.Integer(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_digest_id",
            sa.UUID(),
            sa.ForeignKey("digests.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_digest_schedules_due", "digest_schedules", ["next_run_at"])
    op.create_index("ix_digest_schedules_user", "digest_schedules", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_digest_schedules_user", table_name="digest_schedules")
    op.drop_index("ix_digest_schedules_due", table_name="digest_schedules")
    op.drop_table("digest_schedules")
    op.drop_column("digests", "origin")
    op.drop_table("user_avatars")
