"""a profile's icon and colour, picked by its owner

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-01 20:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The example profiles every guest starts with, and the copies already made.
EXAMPLES = {
    "Специалист по ИБ АСУ ТП": ("shield", "red"),
    "Руководитель ИТ-инфраструктуры": ("servers", "blue"),
    "Директор по цифровой трансформации": ("network", "violet"),
}


def upgrade() -> None:
    op.add_column("profiles", sa.Column("icon", sa.String(length=24), nullable=True))
    op.add_column("profiles", sa.Column("color", sa.String(length=12), nullable=True))
    for name, (icon, color) in EXAMPLES.items():
        op.execute(
            sa.text(
                "UPDATE profiles SET icon = :icon, color = :color "
                "WHERE name = :name AND icon IS NULL"
            ).bindparams(icon=icon, color=color, name=name)
        )


def downgrade() -> None:
    op.drop_column("profiles", "color")
    op.drop_column("profiles", "icon")
