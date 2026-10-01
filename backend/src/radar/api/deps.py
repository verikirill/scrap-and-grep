"""Request-scoped dependencies."""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from radar.auth import sessions as auth_sessions
from radar.auth.sessions import AuthUser
from radar.cache import Cache, get_cache
from radar.config import Settings, get_settings
from radar.db import session_scope


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_scope() as session:
        yield session


# scope="function": commit when the handler returns, before the response is
# sent. With the default scope the commit would run after the client already
# has its 2xx, and a follow-up request could miss the row.
SessionDep = Annotated[AsyncSession, Depends(get_session, scope="function")]
CacheDep = Annotated[Cache, Depends(get_cache)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def client_id(request: Request) -> str:
    """Caller address as seen by the gateway (uvicorn runs with --proxy-headers)."""
    return request.client.host if request.client else "unknown"


def rate_limit(
    bucket: str, per_minute: Callable[[Settings], int]
) -> Callable[..., Awaitable[None]]:
    """Dependency factory: reject callers that exceed `per_minute` requests."""

    async def check(request: Request, cache: CacheDep, settings: SettingsDep) -> None:
        if await cache.hit_rate_limit(f"{bucket}:{client_id(request)}", per_minute(settings)):
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Слишком много запросов, повторите через минуту.",
                headers={"Retry-After": "60"},
            )

    return check


async def optional_user(request: Request, session: SessionDep, cache: CacheDep) -> AuthUser | None:
    """The signed-in reader, or None for a visitor."""
    token = request.cookies.get(auth_sessions.COOKIE_NAME)
    return await auth_sessions.resolve(session, cache, token) if token else None


OptionalUser = Annotated[AuthUser | None, Depends(optional_user)]


async def current_user(user: OptionalUser) -> AuthUser:
    """The signed-in reader, or 401."""
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Войдите, чтобы продолжить.")
    return user


CurrentUser = Annotated[AuthUser, Depends(current_user)]


async def admin_user(user: CurrentUser) -> AuthUser:
    # A guest is never an administrator, whatever its row says.
    if not user.is_admin or user.is_demo:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Это может только администратор.")
    return user


AdminUser = Annotated[AuthUser, Depends(admin_user)]


def user_rate_limit(
    bucket: str, per_minute: Callable[[Settings], int]
) -> Callable[..., Awaitable[None]]:
    """Like `rate_limit`, but counted per account.

    Readers of one company share an address behind NAT, so a per-address limit
    would make them throttle each other.
    """

    async def check(user: CurrentUser, cache: CacheDep, settings: SettingsDep) -> None:
        if await cache.hit_rate_limit(f"{bucket}:u:{user.id}", per_minute(settings)):
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Слишком много запросов, повторите через минуту.",
                headers={"Retry-After": "60"},
            )

    return check
