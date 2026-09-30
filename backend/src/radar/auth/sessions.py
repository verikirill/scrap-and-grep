"""Browser sessions.

The cookie carries a random token. PostgreSQL keeps only its SHA-256, so a
leaked table cannot be replayed as cookies. Any api replica can check a
session; a short-lived cache entry saves the database round trip on the
requests that follow.
"""

import hashlib
import secrets
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from radar.cache import Cache
from radar.db.models import User, UserSession

COOKIE_NAME = "radar_session"
# How long a signed-out or deleted session may still be served from cache by
# a replica that did not see the sign-out. Sign-out itself clears the entry.
CACHE_TTL_SECONDS = 60
_TOKEN_BYTES = 32


@dataclass(frozen=True, slots=True)
class AuthUser:
    """The signed-in reader as the request handlers see them."""

    id: uuid.UUID
    email: str
    display_name: str
    is_admin: bool
    is_demo: bool


def auth_user(user: User) -> AuthUser:
    return AuthUser(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_admin=user.is_admin,
        is_demo=user.is_demo,
    )


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii", "ignore")).hexdigest()


def _cache_key(token_hash: str) -> str:
    return f"session:{token_hash}"


async def start(session: AsyncSession, user: User, ttl_days: int) -> str:
    """Create a session and return the token for the cookie."""
    token = secrets.token_urlsafe(_TOKEN_BYTES)
    session.add(
        UserSession(
            token_hash=_hash(token),
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(days=ttl_days),
        )
    )
    user.last_login_at = datetime.now(UTC)
    await session.flush()
    return token


async def resolve(session: AsyncSession, cache: Cache, token: str) -> AuthUser | None:
    """Who does this cookie belong to, if anyone."""
    # Tokens are 43 URL-safe characters; anything else is not ours.
    if not 20 <= len(token) <= 100:
        return None
    token_hash = _hash(token)
    cached = await cache.get_json(_cache_key(token_hash))
    if cached is not None:
        return AuthUser(**{**cached, "id": uuid.UUID(cached["id"])})
    row = (
        await session.execute(
            select(User)
            .join(UserSession, UserSession.user_id == User.id)
            .where(UserSession.token_hash == token_hash, UserSession.expires_at > datetime.now(UTC))
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    user = auth_user(row)
    await cache.set_json(
        _cache_key(token_hash), {**asdict(user), "id": str(user.id)}, CACHE_TTL_SECONDS
    )
    return user


async def end(session: AsyncSession, cache: Cache, token: str) -> None:
    token_hash = _hash(token)
    await session.execute(delete(UserSession).where(UserSession.token_hash == token_hash))
    await cache.delete(_cache_key(token_hash))


async def end_all(session: AsyncSession, cache: Cache, user_id: uuid.UUID) -> None:
    """Sign the user out everywhere, e.g. before the account is deleted."""
    hashes = (
        await session.execute(
            delete(UserSession)
            .where(UserSession.user_id == user_id)
            .returning(UserSession.token_hash)
        )
    ).scalars()
    await cache.delete(*(_cache_key(token_hash) for token_hash in hashes))


async def purge_expired(session: AsyncSession) -> int:
    result = await session.execute(
        delete(UserSession)
        .where(UserSession.expires_at <= datetime.now(UTC))
        .returning(UserSession.token_hash)
    )
    return len(result.all())
