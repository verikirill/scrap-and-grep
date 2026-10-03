"""who added a source: in an open catalogue its author may change and remove it

Two branches numbered a migration 0026 at once (this one and the digests'
implications), so a database may be stamped 0026 or 0027 while missing a column
the other line of migrations added. Every column of 0026-0028 is therefore
added here only where it is missing, and any database reaches the same schema.

Revision ID: 0028
Revises: 0027
Create Date: 2026-10-12 12:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE sources ADD COLUMN IF NOT EXISTS added_by uuid "
        "REFERENCES users (id) ON DELETE SET NULL"
    )
    op.execute(
        "ALTER TABLE digests ADD COLUMN IF NOT EXISTS implications text[] NOT NULL DEFAULT '{}'"
    )
    op.execute(
        "CREATE TABLE IF NOT EXISTS attack_techniques "
        "(id varchar(16) PRIMARY KEY, name text NOT NULL)"
    )
    op.execute("ALTER TABLE known_exploited_vulnerabilities ADD COLUMN IF NOT EXISTS due_date date")
    op.execute(
        "ALTER TABLE known_exploited_vulnerabilities "
        "ADD COLUMN IF NOT EXISTS cwes text[] NOT NULL DEFAULT '{}'"
    )


def downgrade() -> None:
    op.drop_column("sources", "added_by")
