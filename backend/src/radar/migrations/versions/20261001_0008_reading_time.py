"""length of an article in words, for its reading time

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-01 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The ingest cut texts at 40 000 characters; a cut text is not timed here,
# its page is read again on first need.
CONTENT_LIMIT = 40_000
MIN_WORDS = 80


def upgrade() -> None:
    op.add_column("articles", sa.Column("word_count", sa.Integer(), nullable=True))
    op.add_column("articles", sa.Column("measured_at", sa.DateTime(timezone=True), nullable=True))
    # Words are runs of letters and digits, close to radar.reading: a hyphenated
    # word counts twice here, which moves a reading time by seconds.
    op.execute(
        sa.text(
            """
            UPDATE articles SET word_count = counted.words
            FROM (
                SELECT id,
                       (SELECT count(*) FROM regexp_matches(content, '[[:alnum:]]+', 'g')) AS words
                FROM articles
                WHERE content IS NOT NULL AND length(content) < :limit
            ) AS counted
            WHERE articles.id = counted.id AND counted.words >= :min_words
            """
        ).bindparams(limit=CONTENT_LIMIT, min_words=MIN_WORDS)
    )


def downgrade() -> None:
    op.drop_column("articles", "measured_at")
    op.drop_column("articles", "word_count")
