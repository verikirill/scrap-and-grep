"""Request-scoped dependencies."""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from radar.auth import sessions as auth_sessions
from radar.auth.sessions import AuthUser
from radar.cache import Cache, get_cache
from radar.config import Settings, get_settings
from radar.db import session_scope
from radar.db.models import User


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
                detail="Слишком много запросов. Попробуйте через минуту.",
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
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Действие доступно только администратору."
        )
    return user


AdminUser = Annotated[AuthUser, Depends(admin_user)]


def is_admin(user: AuthUser) -> bool:
    # A guest is never an administrator, whatever its row says.
    return user.is_admin and not user.is_demo


async def catalog_writer(user: CurrentUser, settings: SettingsDep) -> AuthUser:
    """Who may add a source: an administrator, or anyone in an open catalogue."""
    if settings.open_catalog or is_admin(user):
        return user
    raise HTTPException(
        status.HTTP_403_FORBIDDEN, detail="Добавлять источники может только администратор."
    )


CatalogWriter = Annotated[AuthUser, Depends(catalog_writer)]


async def publisher(user: CurrentUser, session: SessionDep) -> AuthUser:
    """Who may run Telegram channels: a reader on their own or the manager of a
    company space. People a company added read; its channels are the manager's."""
    if await session.scalar(select(User.team_id).where(User.id == user.id)) is not None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Каналы ведёт руководитель пространства компании.",
        )
    return user


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
                detail="Слишком много запросов. Попробуйте через минуту.",
                headers={"Retry-After": "60"},
            )

    return check
