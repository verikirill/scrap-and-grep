"""Keys for the MCP server: made, listed and revoked by their owner."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from radar.api.deps import CurrentUser, SessionDep, user_rate_limit
from radar.db.models import ApiKey
from radar.mcp_server import keys

router = APIRouter(prefix="/mcp/keys", tags=["mcp"])

_limit = Depends(user_rate_limit("write", lambda settings: settings.rate_limit_per_minute))
# Making keys is rare: a loop of create and revoke is held to the sign-in pace.
_create_limit = Depends(
    user_rate_limit("mcp-key", lambda settings: settings.auth_rate_limit_per_minute)
)


class KeyIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class KeyOut(BaseModel):
    id: uuid.UUID
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None


class NewKeyOut(KeyOut):
    # Shown once: only its hash is stored.
    token: str


def _out(key: ApiKey) -> KeyOut:
    return KeyOut(
        id=key.id,
        name=key.name,
        prefix=key.prefix,
        created_at=key.created_at,
        last_used_at=key.last_used_at,
    )


@router.get("")
async def list_keys(session: SessionDep, user: CurrentUser) -> list[KeyOut]:
    return [_out(key) for key in await keys.listed(session, user.id)]


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[_create_limit])
async def create_key(payload: KeyIn, session: SessionDep, user: CurrentUser) -> NewKeyOut:
    try:
        key, token = await keys.create(session, user.id, payload.name.strip())
    except keys.TooManyKeys:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=(
                f"В аккаунте уже {keys.MAX_KEYS} ключей. Отзовите ненужный, чтобы создать новый."
            ),
        ) from None
    await session.commit()
    return NewKeyOut(**_out(key).model_dump(), token=token)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_limit])
async def revoke_key(key_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Response:
    if not await keys.revoke(session, user.id, key_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ключ не найден.")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
