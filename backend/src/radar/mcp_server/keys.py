"""Keys readers give their AI assistants to reach the MCP server.

A key is shown once, when it is made; the database keeps its SHA-256 and the
first characters for the owner to tell keys apart. Keys are random enough
(256 bits) that a fast hash is as safe as a slow one would be.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from radar.db.models import ApiKey

KEY_PREFIX = "tng_"
PREFIX_SHOWN = len(KEY_PREFIX) + 6
MAX_KEYS = 10
# The last use is written at most this often: a busy assistant must not
# turn every call into a database write.
USED_AT_STEP = timedelta(minutes=5)


class TooManyKeys(Exception):
    """The reader already has the most keys allowed."""


def hash_key(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create(session: AsyncSession, user_id: uuid.UUID, name: str) -> tuple[ApiKey, str]:
    """A new key: the row, and the key itself, which is not stored."""
    active = await session.scalar(
        select(func.count())
        .select_from(ApiKey)
        .where(ApiKey.user_id == user_id, ApiKey.revoked_at.is_(None))
    )
    if (active or 0) >= MAX_KEYS:
        raise TooManyKeys
    token = KEY_PREFIX + secrets.token_urlsafe(32)
    key = ApiKey(
        id=uuid.uuid7(),
        user_id=user_id,
        name=name,
        prefix=token[:PREFIX_SHOWN],
        token_hash=hash_key(token),
        created_at=datetime.now(UTC),
    )
    session.add(key)
    await session.flush()
    return key, token


async def listed(session: AsyncSession, user_id: uuid.UUID) -> list[ApiKey]:
    statement = (
        select(ApiKey)
        .where(ApiKey.user_id == user_id, ApiKey.revoked_at.is_(None))
        .order_by(ApiKey.created_at.desc())
    )
    return list((await session.scalars(statement)).all())


async def revoke(session: AsyncSession, user_id: uuid.UUID, key_id: uuid.UUID) -> bool:
    result = await session.execute(
        update(ApiKey)
        .where(ApiKey.id == key_id, ApiKey.user_id == user_id, ApiKey.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
        .returning(ApiKey.id)
    )
    return result.scalar_one_or_none() is not None


async def owner(
    session: AsyncSession, token: str, *, now: datetime | None = None
) -> uuid.UUID | None:
    """The reader a key belongs to; None for an unknown or revoked key."""
    if not token.startswith(KEY_PREFIX):
        return None
    key = await session.scalar(
        select(ApiKey).where(ApiKey.token_hash == hash_key(token), ApiKey.revoked_at.is_(None))
    )
    if key is None:
        return None
    now = now or datetime.now(UTC)
    if key.last_used_at is None or now - key.last_used_at > USED_AT_STEP:
        key.last_used_at = now
    return key.user_id
