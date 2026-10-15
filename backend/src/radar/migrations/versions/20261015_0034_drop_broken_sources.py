"""default sources whose pages no longer give articles

dbugs PT, the trending vulnerabilities of PT and the news of the ICS BDU
changed their markup: every round ended in MarkupChanged. The defaults no
longer carry them, and a stack that has them drops them with their articles.

Revision ID: 0034
Revises: 0033
Create Date: 2026-10-15 18:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SLUGS = ("dbugs-pt", "pt-trending", "bdu-asutp")


def upgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM sources WHERE added_by IS NULL AND slug = ANY(:slugs)"),
        {"slugs": list(SLUGS)},
    )


def downgrade() -> None:
    # The next start seeds nothing back: the defaults no longer list them.
    pass
