"""company spaces: teams, accounts made for their people, invitations

Revision ID: 0038
Revises: 0037
Create Date: 2026-10-16 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("about", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "teams",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("services", sa.Text(), nullable=False, server_default=""),
        sa.Column("spec", postgresql.JSONB(), nullable=False),
        sa.Column("icon", sa.String(24), nullable=True),
        sa.Column("color", sa.String(12), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_teams_company", "teams", ["company_id", "created_at"])

    op.add_column(
        "users",
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("users", sa.Column("job_title", sa.String(120), nullable=True))
    op.add_column("users", sa.Column("invite_token", sa.String(64), nullable=True))
    op.add_column(
        "users", sa.Column("invite_expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_unique_constraint("users_invite_token_key", "users", ["invite_token"])
    op.create_index("ix_users_team", "users", ["team_id"])

    op.add_column(
        "profiles",
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_profiles_team", "profiles", ["team_id"])


def downgrade() -> None:
    op.drop_index("ix_profiles_team", table_name="profiles")
    op.drop_column("profiles", "team_id")
    op.drop_index("ix_users_team", table_name="users")
    op.drop_constraint("users_invite_token_key", "users", type_="unique")
    for column in ("invite_expires_at", "invite_token", "job_title", "team_id"):
        op.drop_column("users", column)
    op.drop_index("ix_teams_company", table_name="teams")
    op.drop_table("teams")
    op.drop_table("companies")
