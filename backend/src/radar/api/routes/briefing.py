"""Spoken briefs of management digests: order one, follow it, listen to it."""

import asyncio
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, StringConstraints
from sqlalchemy.ext.asyncio import AsyncSession

from radar.api.deps import CacheDep, CurrentUser, SessionDep, SettingsDep, user_rate_limit
from radar.auth.sessions import AuthUser
from radar.briefing import service
from radar.db.models import Briefing, Digest
from radar.logging import get_logger
from radar.shorts.model import ACTIVE_STATUSES, STATUS_DONE, STATUS_FAILED
from radar.shorts.service import known_voices
from radar.shorts.voice import VOICE_ID_PATTERN, VoiceOption
from radar.store import digests as digest_store
from radar.worker.tasks import make_briefing

router = APIRouter(tags=["briefing"])
log = get_logger(__name__)

# Voicing a brief is as heavy as voicing a video: the same limit.
_briefing_limit = Depends(
    user_rate_limit("briefing", lambda settings: settings.short_rate_limit_per_minute)
)


class BriefingCreate(BaseModel):
    # One of the voices in BriefingState; none is the voice service's default.
    voice: Annotated[str, StringConstraints(pattern=VOICE_ID_PATTERN)] | None = None


class BriefingOut(BaseModel):
    status: str
    progress: float
    error: str | None
    voice: str | None
    requested_voice: str | None
    # What is said, line by line: the transcript under the player.
    lines: list[str]
    duration_ms: int | None
    size_bytes: int | None
    created_at: datetime
    finished_at: datetime | None
    # Where to listen to it, once it is done. The version parameter makes the
    # browser drop a cached copy of an earlier recording.
    url: str | None


class BriefingState(BaseModel):
    # False when the server has no voice service: the player is not shown.
    available: bool
    # Voices a reader can pick; empty when the voice service offers no choice
    # or the media worker has not reported them yet.
    voices: list[VoiceOption] = []
    briefing: BriefingOut | None = None


def _out(briefing: Briefing) -> BriefingOut:
    url = None
    if briefing.status == STATUS_DONE and briefing.finished_at is not None:
        version = int(briefing.finished_at.timestamp())
        url = f"/api/v1/digests/{briefing.digest_id}/briefing.wav?v={version}"
    # A brief no worker finished is shown as failed, so it can be ordered again.
    stale = briefing.status in ACTIVE_STATUSES and not service.is_active(briefing)
    return BriefingOut(
        status=STATUS_FAILED if stale else briefing.status,
        progress=briefing.progress,
        error=service.GENERIC_FAILURE if stale else briefing.error,
        voice=briefing.voice,
        requested_voice=briefing.requested_voice,
        lines=list(briefing.lines or []),
        duration_ms=briefing.duration_ms,
        size_bytes=briefing.size_bytes,
        created_at=briefing.created_at,
        finished_at=briefing.finished_at,
        url=url,
    )


async def _management_digest(session: AsyncSession, user: AuthUser, digest_id: uuid.UUID) -> Digest:
    digest = await digest_store.get(session, digest_id, user_id=user.id)
    if digest is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Выпуск не найден.")
    if digest.profile_spec.get("audience") != "management":
        raise HTTPException(status.HTTP_409_CONFLICT, detail=service.MANAGEMENT_ONLY)
    return digest


@router.get("/digests/{digest_id}/briefing")
async def get_briefing(
    digest_id: uuid.UUID,
    session: SessionDep,
    settings: SettingsDep,
    cache: CacheDep,
    user: CurrentUser,
) -> BriefingState:
    """Whether a brief can be voiced here, the voices to pick from and the
    digest's brief with its progress, `null` if none was ordered."""
    await _management_digest(session, user, digest_id)
    if not settings.tts_url:
        return BriefingState(available=False)
    briefing = await service.get(session, digest_id, user.id)
    return BriefingState(
        available=True,
        voices=await known_voices(cache),
        briefing=_out(briefing) if briefing is not None else None,
    )


@router.post(
    "/digests/{digest_id}/briefing",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[_briefing_limit],
)
async def create_briefing(
    digest_id: uuid.UUID,
    session: SessionDep,
    settings: SettingsDep,
    cache: CacheDep,
    user: CurrentUser,
    payload: BriefingCreate | None = None,
) -> BriefingOut:
    """Queue the spoken brief of a finished management digest. A new request
    replaces the previous brief of the same digest."""
    if not settings.tts_url:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=service.NO_VOICE)
    digest = await _management_digest(session, user, digest_id)
    if digest.status != digest_store.STATUS_DONE:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Выпуск ещё не готов.")
    voice = payload.voice if payload is not None else None
    known = {item.id for item in await known_voices(cache)}
    # With no list at hand the voice is taken on trust: the worker falls back
    # to the default if the service refuses it.
    if voice is not None and known and voice not in known:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Такого голоса нет.")
    current = await service.get(session, digest_id, user.id)
    if current is not None and service.is_active(current):
        return _out(current)
    if await service.count_active(session) >= settings.max_active_shorts:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Сервис синтеза речи перегружен. Попробуйте через пару минут.",
            headers={"Retry-After": "120"},
        )
    try:
        briefing = await service.request(session, digest_id, user.id, voice)
    except service.AlreadyMaking as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Уже озвучивается брифинг для другого выпуска. Дождитесь его готовности.",
            headers={"Retry-After": "60"},
        ) from exc
    if briefing is None:
        # Another request for this digest got there first.
        running = await service.get(session, digest_id, user.id)
        if running is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Выпуск не найден.")
        return _out(running)
    # The worker must find the row, so commit before the task is queued.
    await session.commit()
    try:
        await make_briefing.kiq(str(briefing.id))
    except Exception as exc:
        log.exception("briefing_enqueue_failed", briefing_id=str(briefing.id))
        await service.fail(briefing.id, "Очередь задач недоступна. Попробуйте позже.")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="Очередь задач недоступна."
        ) from exc
    return _out(briefing)


@router.get("/digests/{digest_id}/briefing.wav", response_class=FileResponse)
async def listen_briefing(
    digest_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    download: Annotated[bool, Query()] = False,
) -> FileResponse:
    """The WAV itself. Range requests are served, so the player can seek."""
    briefing = await service.get(session, digest_id, user.id)
    path = service.audio_path(briefing.id) if briefing is not None else None
    if (
        briefing is None
        or briefing.status != STATUS_DONE
        or path is None
        or not await asyncio.to_thread(path.is_file)
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Брифинг не найден.")
    finished = briefing.finished_at or briefing.created_at
    return FileResponse(
        path,
        media_type="audio/wav",
        filename=f"radar-briefing-{finished:%Y-%m-%d}.wav",
        content_disposition_type="attachment" if download else "inline",
        headers={"Cache-Control": "private, no-store"},
    )
