"""accounts, resumes and reader signals

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-30 21:10:00
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Profiles and digests created before accounts existed go to the demo account.
# Nobody signs in to it: its profiles are the examples every guest starts with.
DEMO_EMAIL = "demo@radar.local"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("is_admin", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_demo", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_index("ix_sessions_user", "sessions", ["user_id"])
    op.create_index("ix_sessions_expires", "sessions", ["expires_at"])

    op.create_table(
        "resumes",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("file_format", sa.String(length=16), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("payload", sa.LargeBinary(), nullable=True),
        sa.Column("parser", sa.String(length=32), nullable=True),
        sa.Column("facts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("suggestion", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "interactions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("article_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("context", sa.String(length=16), server_default="feed", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "article_id", "kind", name="uq_interactions_user_article_kind"
        ),
    )
    op.create_index("ix_interactions_user_created", "interactions", ["user_id", "created_at"])
    op.create_index(
        "uq_interactions_verdict",
        "interactions",
        ["user_id", "article_id"],
        unique=True,
        postgresql_where=sa.text("kind IN ('like', 'dislike')"),
    )
    op.create_index("ix_interactions_article", "interactions", ["article_id"])
    op.create_table(
        "user_vectors",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=1024), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "model"),
    )

    op.add_column(
        "digest_items",
        sa.Column("personal", sa.Float(), server_default="0", nullable=False),
    )
    op.add_column(
        "digest_items",
        sa.Column("personal_note", sa.Text(), server_default="", nullable=False),
    )

    # uuidv7() is built into PostgreSQL 18, the version the stack ships.
    op.execute(
        sa.text(
            "INSERT INTO users (id, email, display_name, is_admin, is_demo) "
            "VALUES (uuidv7(), :email, 'Примеры', false, true)"
        ).bindparams(email=DEMO_EMAIL)
    )
    for table in ("profiles", "digests"):
        op.add_column(table, sa.Column("user_id", sa.UUID(), nullable=True))
        op.execute(
            sa.text(
                f"UPDATE {table} SET user_id = (SELECT id FROM users WHERE email = :email)"  # noqa: S608
            ).bindparams(email=DEMO_EMAIL)
        )
        op.alter_column(table, "user_id", nullable=False)
        op.create_foreign_key(
            f"fk_{table}_user", table, "users", ["user_id"], ["id"], ondelete="CASCADE"
        )
        op.create_index(f"ix_{table}_user_created", table, ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_column("digest_items", "personal_note")
    op.drop_column("digest_items", "personal")
    for table in ("digests", "profiles"):
        op.drop_index(f"ix_{table}_user_created", table_name=table)
        op.drop_constraint(f"fk_{table}_user", table, type_="foreignkey")
        op.drop_column(table, "user_id")
    op.drop_table("user_vectors")
    op.drop_index("ix_interactions_article", table_name="interactions")
    op.drop_index("uq_interactions_verdict", table_name="interactions")
    op.drop_index("ix_interactions_user_created", table_name="interactions")
    op.drop_table("interactions")
    op.drop_table("resumes")
    op.drop_index("ix_sessions_expires", table_name="sessions")
    op.drop_index("ix_sessions_user", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")
