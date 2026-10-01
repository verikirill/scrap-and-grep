"""Short videos of digests: order one, follow it, watch or download it."""

import asyncio
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, StringConstraints

from radar.api.deps import CacheDep, CurrentUser, SessionDep, SettingsDep, user_rate_limit
from radar.db.models import Video
from radar.logging import get_logger
from radar.shorts import service
from radar.shorts.model import ACTIVE_STATUSES, STATUS_DONE
from radar.shorts.voice import VOICE_ID_PATTERN
from radar.store import digests as digest_store
from radar.worker.tasks import make_short

router = APIRouter(tags=["shorts"])
log = get_logger(__name__)

_short_limit = Depends(
    user_rate_limit("short", lambda settings: settings.short_rate_limit_per_minute)
)


class ShortCreate(BaseModel):
    # One of meta.short_voices; none is the voice service's default.
    voice: Annotated[str, StringConstraints(pattern=VOICE_ID_PATTERN)] | None = None


class VideoOut(BaseModel):
    status: str
    stage: str | None
    progress: float
    error: str | None
    voice: str | None
    # The voice the reader picked, as in meta.short_voices.
    requested_voice: str | None
    by_model: bool
    duration_ms: int | None
    size_bytes: int | None
    created_at: datetime
    finished_at: datetime | None
    # Where to watch it, once it is done. The version parameter makes the
    # browser drop a cached copy of an earlier cut.
    url: str | None


def _out(video: Video) -> VideoOut:
    url = None
    if video.status == STATUS_DONE and video.finished_at is not None:
        url = f"/api/v1/digests/{video.digest_id}/short.mp4?v={int(video.finished_at.timestamp())}"
    return VideoOut(
        status=video.status,
        stage=video.stage,
        progress=video.progress,
        error=video.error,
        voice=video.voice,
        requested_voice=video.requested_voice,
        by_model=video.by_model,
        duration_ms=video.duration_ms,
        size_bytes=video.size_bytes,
        created_at=video.created_at,
        finished_at=video.finished_at,
        url=url,
    )


@router.post(
    "/digests/{digest_id}/short", status_code=status.HTTP_202_ACCEPTED, dependencies=[_short_limit]
)
async def create_short(
    digest_id: uuid.UUID,
    session: SessionDep,
    settings: SettingsDep,
    cache: CacheDep,
    user: CurrentUser,
    payload: ShortCreate | None = None,
) -> VideoOut:
    """Queue a short video of a finished digest. A new request replaces the
    previous video of the same digest."""
    if not settings.shorts_url:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="Видео на этом сервере выключено."
        )
    digest = await digest_store.get(session, digest_id, user_id=user.id)
    if digest is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Дайджест не найден.")
    if digest.status != digest_store.STATUS_DONE:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Дайджест ещё не готов.")
    voice = payload.voice if payload is not None else None
    known = {item.id for item in await service.known_voices(cache)}
    # With no list at hand (the worker has not reported yet) the voice is
    # taken on trust: the worker falls back to the default if it is refused.
    if voice is not None and known and voice not in known:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Такого голоса нет.")
    current = await service.get(session, digest_id, user.id)
    if current is not None and current.status in ACTIVE_STATUSES:
        return _out(current)
    # A safety cap for the whole server; one reader is held to one video at a
    # time by the database itself (see service.request).
    if await service.count_active(session) >= settings.max_active_shorts:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Сейчас собирается много видео. Попробуйте через пару минут.",
            headers={"Retry-After": "120"},
        )
    try:
        video = await service.request(session, digest_id, user.id, voice)
    except service.AlreadyMaking as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Уже собирается видео другого выпуска. Дождитесь, пока оно будет готово.",
            headers={"Retry-After": "60"},
        ) from exc
    if video is None:
        # Another request for this digest got there first.
        running = await service.get(session, digest_id, user.id)
        if running is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Дайджест не найден.")
        return _out(running)
    # The worker must find the row, so commit before the task is queued.
    await session.commit()
    try:
        await make_short.kiq(str(video.id))
    except Exception as exc:
        log.exception("short_enqueue_failed", video_id=str(video.id))
        await service.fail(video.id, "Очередь задач недоступна. Повторите позже.")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="Очередь задач недоступна."
        ) from exc
    return _out(video)


@router.get("/digests/{digest_id}/short")
async def get_short(
    digest_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> VideoOut | None:
    """The video of a digest and its progress, or `null` if none was ordered."""
    video = await service.get(session, digest_id, user.id)
    return _out(video) if video is not None else None


@router.get("/digests/{digest_id}/short.mp4", response_class=FileResponse)
async def watch_short(
    digest_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    download: Annotated[bool, Query()] = False,
) -> FileResponse:
    """The MP4 itself. Range requests are served, so the player can seek."""
    video = await service.get(session, digest_id, user.id)
    path = service.video_path(video.id) if video is not None else None
    if (
        video is None
        or video.status != STATUS_DONE
        or path is None
        or not await asyncio.to_thread(path.is_file)
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Видео не найдено.")
    finished = video.finished_at or video.created_at
    return FileResponse(
        path,
        media_type="video/mp4",
        filename=f"radar-short-{finished:%Y-%m-%d}.mp4",
        content_disposition_type="attachment" if download else "inline",
        # Nothing is left in the browser cache of a shared computer after
        # sign-out; seeking works through range requests anyway.
        headers={"Cache-Control": "private, no-store"},
    )
