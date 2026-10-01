"""Locking a reader's profiles, and the impressions kept for them."""

import uuid
from datetime import datetime

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from radar.db.models import Impression


async def lock_profiles(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Hold the reader's profile list until the transaction ends.

    Every change to a reader's profiles takes it: creating one, accepting a
    shared one or a suggestion, a reset, the background adaptation writing
    what it learned. Without it two of them could each read the profiles,
    then write over the other's change.
    """
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))").bindparams(key=f"profiles:{user_id}")
    )


async def purge_impressions(session: AsyncSession, before: datetime) -> int:
    """Impressions older than adaptation looks back are of no use."""
    result = await session.execute(delete(Impression).where(Impression.last_seen_at < before))
    return int(getattr(result, "rowcount", 0) or 0)
