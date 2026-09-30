"""Request-scoped dependencies."""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from radar.cache import Cache, get_cache
from radar.config import Settings, get_settings
from radar.db import session_scope


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_scope() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
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
