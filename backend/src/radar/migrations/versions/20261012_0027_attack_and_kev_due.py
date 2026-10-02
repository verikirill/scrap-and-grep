"""ATT&CK techniques for the check of attack cards; the KEV due date and CWE

Revision ID: 0027
Revises: 0026
Create Date: 2026-10-12 11:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "attack_techniques",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
    )
    op.add_column("known_exploited_vulnerabilities", sa.Column("due_date", sa.Date()))
    op.add_column(
        "known_exploited_vulnerabilities",
        sa.Column("cwes", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("known_exploited_vulnerabilities", "cwes")
    op.drop_column("known_exploited_vulnerabilities", "due_date")
    op.drop_table("attack_techniques")
