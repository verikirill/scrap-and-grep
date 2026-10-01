"""Short video lifecycle: request, script, voice, render, file on disk."""

import asyncio
import os
import time
import uuid
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from radar.ai.factory import get_breaker, get_chat
from radar.cache import Cache
from radar.config import get_settings
from radar.db import session_scope
from radar.db.models import Video
from radar.logging import get_logger
from radar.shorts.model import (
    ACTIVE_STATUSES,
    STAGE_RENDER,
    STAGE_SCRIPT,
    STAGE_VOICE,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_QUEUED,
    STATUS_RUNNING,
    ShortError,
)
from radar.shorts.renderer import RendererBusy, RendererRejected, render
from radar.shorts.script import (
    HeuristicScriptWriter,
    ResilientScriptWriter,
    ScriptWriter,
    pick_items,
)
from radar.shorts.timing import build_props, format_period
from radar.shorts.voice import VoiceClient, VoiceOption, narrate
from radar.store import digests as digest_store
from radar.views import digest_view

log = get_logger(__name__)

GENERIC_FAILURE = "Не удалось собрать видео. Попробуйте ещё раз."
_PARTIAL_SUFFIX = ".part"
LEFTOVER_SECONDS = 3600
RENDER_BUSY_ATTEMPTS = 4
RENDER_BUSY_WAIT_SECONDS = 30
# The voices of the voice service, as the media worker last heard them. The
# housekeeping round refreshes them every 10 minutes; a list nobody has
# confirmed for three rounds is dropped.
VOICES_KEY = "shorts:voices"
VOICES_TTL_SECONDS = 30 * 60


@lru_cache
def get_writer() -> ScriptWriter:
    fallback = HeuristicScriptWriter()
    chat = get_chat()
    if chat is None:
        return fallback

    from radar.shorts.script import OllamaScriptWriter

    return ResilientScriptWriter(OllamaScriptWriter(chat), fallback, get_breaker())


def get_voice() -> VoiceClient | None:
    settings = get_settings()
    if not settings.tts_url:
        return None
    return VoiceClient(
        settings.tts_url, timeout=settings.tts_timeout_seconds, speaker=settings.tts_voice
    )


async def refresh_voices(cache: Cache) -> list[VoiceOption]:
    """Ask the voice service which voices it offers and remember the answer
    for the api, which has no route to the service."""
    client = get_voice()
    voices = await client.voices() if client is not None else []
    await cache.set_json(VOICES_KEY, [voice.model_dump() for voice in voices], VOICES_TTL_SECONDS)
    return voices


async def known_voices(cache: Cache) -> list[VoiceOption]:
    """The voices the media worker last heard of; empty if it has not said."""
    cached = await cache.get_json(VOICES_KEY)
    return [VoiceOption.model_validate(item) for item in cached] if isinstance(cached, list) else []


def media_root() -> Path:
    return Path(get_settings().media_dir) / "shorts"


def video_path(video_id: uuid.UUID) -> Path:
    return media_root() / f"{video_id}.mp4"


async def get(session: AsyncSession, digest_id: uuid.UUID, user_id: uuid.UUID) -> Video | None:
    """The reader's video of a digest; someone else's is reported as missing."""
    return (
        await session.execute(
            select(Video).where(Video.digest_id == digest_id, Video.user_id == user_id)
        )
    ).scalar_one_or_none()


async def count_active(session: AsyncSession) -> int:
    """Videos queued or being made, across all readers."""
    statement = select(func.count()).select_from(Video).where(Video.status.in_(ACTIVE_STATUSES))
    return int(await session.scalar(statement) or 0)


class AlreadyMaking(Exception):
    """The reader already has a video queued or being made."""


async def request(
    session: AsyncSession, digest_id: uuid.UUID, user_id: uuid.UUID, voice: str | None = None
) -> Video | None:
    """Queue a video of the digest, replacing a finished or failed one.

    Returns None when the digest's video is already queued or being made: two
    presses, or two tabs, must not reset a video half way. Raises
    `AlreadyMaking` when the reader has another digest's video in the works.
    Both rules are enforced by the database, so racing requests cannot pass.

    The row gets a new id on every request. A task left over from the previous
    request then finds nothing to do, and the previous file becomes a stray
    that the purge removes.
    """
    values = {
        "id": uuid.uuid7(),
        "status": STATUS_QUEUED,
        "stage": None,
        "progress": 0.0,
        "error": None,
        "script": None,
        "voice": None,
        "requested_voice": voice,
        "by_model": False,
        "duration_ms": None,
        "size_bytes": None,
        "created_at": datetime.now(UTC),
        "finished_at": None,
    }
    statement = (
        insert(Video)
        .values(digest_id=digest_id, user_id=user_id, **values)
        .on_conflict_do_update(
            index_elements=["digest_id"],
            set_=values,
            where=Video.status.not_in(ACTIVE_STATUSES),
        )
        .returning(Video)
    )
    try:
        # A savepoint, so that a refusal leaves the request's session usable.
        async with session.begin_nested():
            return (await session.execute(statement)).scalar_one_or_none()
    except IntegrityError as exc:
        if "uq_videos_user_active" in str(exc.orig):
            raise AlreadyMaking from exc
        raise


async def _update(video_id: uuid.UUID, **values: object) -> None:
    async with session_scope() as session:
        await session.execute(update(Video).where(Video.id == video_id).values(**values))


async def fail(video_id: uuid.UUID, message: str = GENERIC_FAILURE) -> None:
    await _update(
        video_id,
        status=STATUS_FAILED,
        stage=None,
        error=message[:500],
        finished_at=datetime.now(UTC),
    )


def _write(path: Path, data: bytes) -> None:
    """Write next to the target and rename, so a reader never sees half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + _PARTIAL_SUFFIX)
    partial.write_bytes(data)
    os.replace(partial, path)


async def _render_when_free(url: str, props: dict[str, Any], audio: bytes | None) -> bytes:
    """Render, waiting while the renderer's queue is full.

    The queue retries a failed task at once (taskiq's retry delay needs a
    schedule source this project does not run), and a busy renderer stays
    busy for minutes, so the wait happens here.
    """
    timeout = get_settings().shorts_timeout_seconds
    for _ in range(RENDER_BUSY_ATTEMPTS - 1):
        try:
            return await render(url, props, audio, request_timeout=timeout)
        except RendererBusy:
            await asyncio.sleep(RENDER_BUSY_WAIT_SECONDS)
    return await render(url, props, audio, request_timeout=timeout)


async def process(video_id: uuid.UUID) -> bool:
    """Make one video. Returns False when there was nothing to do: the request
    was deleted or already handled.

    A `ShortError` is final and is shown to the reader. Any other exception
    propagates so the queue can retry; the caller records the failure after
    the last attempt.
    """
    settings = get_settings()
    async with session_scope() as session:
        row = await session.get(Video, video_id)
        if row is None or row.status not in ACTIVE_STATUSES:
            return False
        digest = await digest_store.get(session, row.digest_id, full=True)
        if digest is None:
            return False
        view = digest_view(digest)
        voice = row.requested_voice
        row.status, row.stage, row.progress = STATUS_RUNNING, STAGE_SCRIPT, 0.1

    try:
        items = pick_items(view, settings.shorts_max_items)
        script = await get_writer().write(view, items)
        await _update(video_id, stage=STAGE_VOICE, progress=0.3)
        narration = await narrate(get_voice(), script.lines(), voice)
        props = build_props(
            script,
            narration,
            period=format_period(view.period_start, view.period_end),
            audience=view.profile.name,
        )
        await _update(video_id, stage=STAGE_RENDER, progress=0.55)
        video = await _render_when_free(settings.shorts_url, props, narration.audio)
    except ShortError as exc:
        await fail(video_id, str(exc))
        return True
    except RendererRejected:
        await fail(video_id)
        return True

    await asyncio.to_thread(_write, video_path(video_id), video)
    await _update(
        video_id,
        status=STATUS_DONE,
        stage=None,
        progress=1.0,
        error=None,
        script={**script.model_dump(mode="json"), "timeline": props},
        voice=narration.voice,
        by_model=script.by_model,
        duration_ms=props["durationMs"],
        size_bytes=len(video),
        finished_at=datetime.now(UTC),
    )
    log.info(
        "short_done",
        video_id=str(video_id),
        beats=len(script.beats),
        by_model=script.by_model,
        voice=narration.voice,
        duration_ms=props["durationMs"],
        size_bytes=len(video),
    )
    return True


async def fail_stale(session: AsyncSession, older_than: datetime) -> int:
    """Give up on videos no worker finished."""
    result = await session.execute(
        update(Video)
        .where(Video.status.in_(ACTIVE_STATUSES), Video.created_at < older_than)
        .values(
            status=STATUS_FAILED, stage=None, error=GENERIC_FAILURE, finished_at=datetime.now(UTC)
        )
        .returning(Video.id)
    )
    return len(result.all())


def _is_stray(path: Path, known: dict[str, str], now: float) -> bool:
    video_id = path.name.removesuffix(_PARTIAL_SUFFIX).removesuffix(".mp4")
    if video_id not in known:
        # The digest or the reader is gone, or the video was made again
        # under a new id.
        return True
    # A half-written file of a crashed worker, or a file written after its
    # row was already given up on: both are left alone for an hour, in
    # case the work is still going on.
    is_leftover = path.name.endswith(_PARTIAL_SUFFIX) or known[video_id] != STATUS_DONE
    return is_leftover and now - path.stat().st_mtime > LEFTOVER_SECONDS


def _stray_files(known: dict[str, str]) -> list[Path]:
    root = media_root()
    if not root.is_dir():
        return []
    now = time.time()
    return [path for path in root.iterdir() if path.is_file() and _is_stray(path, known, now)]


async def purge_files() -> int:
    """Delete videos whose digest or reader is gone, and leftovers of failed work."""
    async with session_scope() as session:
        rows = await session.execute(select(Video.id, Video.status))
        known = {str(video_id): status for video_id, status in rows}
    stray = await asyncio.to_thread(_stray_files, known)
    for path in stray:
        await asyncio.to_thread(path.unlink, missing_ok=True)
    return len(stray)
