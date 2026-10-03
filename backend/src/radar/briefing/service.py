"""Brief lifecycle: request, script, voice in parts, a WAV file on disk.

It follows the short videos (radar.shorts.service): the same queue and media
worker, the same voice service and voice choice, a row per digest replaced
by a new request, one brief in the works per reader.
"""

import asyncio
import io
import os
import time
import uuid
import wave
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from radar.briefing.script import BriefingError, build_script
from radar.config import get_settings
from radar.db import session_scope
from radar.db.models import Briefing
from radar.logging import get_logger
from radar.shorts.model import (
    ACTIVE_STATUSES,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_QUEUED,
    STATUS_RUNNING,
)
from radar.shorts.service import get_voice
from radar.shorts.voice import GAP_MS, VoiceClient
from radar.store import digests as digest_store
from radar.views import digest_view
from radar.worker.brokers import MEDIA_IDLE_TIMEOUT_MS

log = get_logger(__name__)

GENERIC_FAILURE = "Не удалось озвучить брифинг. Попробуйте ещё раз."
MANAGEMENT_ONLY = "Брифинг есть только у выпуска для руководства."
NO_VOICE = "Голос на этом сервере не подключён."
# Lines sent to the voice service at once. It takes twelve, but on a CPU one
# request of a whole brief outlasts its timeout; parts also move the progress.
PART_LINES = 4
# A redelivered task may run for as long again; a brief left in the works
# after that is given up on, so that the reader can order a new one.
STALE_AFTER = timedelta(milliseconds=2 * MEDIA_IDLE_TIMEOUT_MS)
_PARTIAL_SUFFIX = ".part"
LEFTOVER_SECONDS = 3600


def media_root() -> Path:
    return Path(get_settings().media_dir) / "briefings"


def audio_path(briefing_id: uuid.UUID) -> Path:
    return media_root() / f"{briefing_id}.wav"


def is_active(briefing: Briefing, now: datetime | None = None) -> bool:
    """Queued or being voiced, and not yet given up on."""
    now = now or datetime.now(UTC)
    return briefing.status in ACTIVE_STATUSES and briefing.created_at >= now - STALE_AFTER


async def get(session: AsyncSession, digest_id: uuid.UUID, user_id: uuid.UUID) -> Briefing | None:
    """The reader's brief of a digest; someone else's is reported as missing."""
    return (
        await session.execute(
            select(Briefing).where(Briefing.digest_id == digest_id, Briefing.user_id == user_id)
        )
    ).scalar_one_or_none()


async def count_active(session: AsyncSession) -> int:
    """Briefs queued or being voiced, across all readers."""
    statement = (
        select(func.count()).select_from(Briefing).where(Briefing.status.in_(ACTIVE_STATUSES))
    )
    return int(await session.scalar(statement) or 0)


class AlreadyMaking(Exception):
    """The reader already has a brief queued or being voiced."""


async def _fail_stale(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(
        update(Briefing)
        .where(
            Briefing.user_id == user_id,
            Briefing.status.in_(ACTIVE_STATUSES),
            Briefing.created_at < datetime.now(UTC) - STALE_AFTER,
        )
        .values(status=STATUS_FAILED, error=GENERIC_FAILURE, finished_at=datetime.now(UTC))
    )


async def request(
    session: AsyncSession, digest_id: uuid.UUID, user_id: uuid.UUID, voice: str | None = None
) -> Briefing | None:
    """Queue a brief of the digest, replacing a finished or failed one.

    Returns None when the digest's brief is already in the works; raises
    `AlreadyMaking` when the reader has another digest's brief in the works.
    Both rules are kept by the database, so racing requests cannot pass. The
    row gets a new id each time, so a task left over from the previous
    request finds nothing to do and the previous file becomes a stray.
    """
    await _fail_stale(session, user_id)
    values = {
        "id": uuid.uuid7(),
        "status": STATUS_QUEUED,
        "progress": 0.0,
        "error": None,
        "lines": [],
        "voice": None,
        "requested_voice": voice,
        "duration_ms": None,
        "size_bytes": None,
        "created_at": datetime.now(UTC),
        "finished_at": None,
    }
    statement = (
        insert(Briefing)
        .values(digest_id=digest_id, user_id=user_id, **values)
        .on_conflict_do_update(
            index_elements=["digest_id"],
            set_=values,
            where=Briefing.status.not_in(ACTIVE_STATUSES),
        )
        .returning(Briefing)
    )
    try:
        # A savepoint, so that a refusal leaves the request's session usable.
        async with session.begin_nested():
            return (await session.execute(statement)).scalar_one_or_none()
    except IntegrityError as exc:
        if "uq_briefings_user_active" in str(exc.orig):
            raise AlreadyMaking from exc
        raise


async def _update(briefing_id: uuid.UUID, **values: object) -> None:
    async with session_scope() as session:
        await session.execute(update(Briefing).where(Briefing.id == briefing_id).values(**values))


async def fail(briefing_id: uuid.UUID, message: str = GENERIC_FAILURE) -> None:
    await _update(
        briefing_id, status=STATUS_FAILED, error=message[:500], finished_at=datetime.now(UTC)
    )


def join_wav(parts: Sequence[bytes], gap_ms: int) -> bytes:
    """One WAV of the parts in their order, with a pause between them."""
    out = io.BytesIO()
    with wave.open(out, "wb") as writer:
        layout: tuple[int, int, int] | None = None
        for data in parts:
            with wave.open(io.BytesIO(data), "rb") as reader:
                current = (reader.getnchannels(), reader.getsampwidth(), reader.getframerate())
                if layout is None:
                    layout = current
                    writer.setnchannels(current[0])
                    writer.setsampwidth(current[1])
                    writer.setframerate(current[2])
                elif current != layout:
                    raise ValueError("the parts of the brief came in different formats")
                else:
                    channels, width, rate = layout
                    writer.writeframes(b"\x00" * (rate * gap_ms // 1000) * channels * width)
                writer.writeframes(reader.readframes(reader.getnframes()))
    return out.getvalue()


def duration_ms(data: bytes) -> int:
    with wave.open(io.BytesIO(data), "rb") as reader:
        return reader.getnframes() * 1000 // reader.getframerate()


async def speak(
    client: VoiceClient,
    lines: Sequence[str],
    voice: str | None,
    on_part: Callable[[int, int], Awaitable[None]] | None = None,
) -> tuple[bytes, str | None]:
    """Voice the lines a few at a time and join the parts. Returns the WAV and
    the voice that read it.

    A picked voice the service refuses (removed after the reader chose it)
    gives way to its default voice. Any other failure propagates: a brief
    without a voice is no brief, so the queue tries again.
    """
    parts: list[bytes] = []
    used: str | None = None
    total = -(-len(lines) // PART_LINES)
    for start in range(0, len(lines), PART_LINES):
        chunk = list(lines[start : start + PART_LINES])
        try:
            narration = await client.speak(chunk, voice)
        except httpx.HTTPStatusError as exc:
            if voice is None or exc.response.status_code != httpx.codes.BAD_REQUEST:
                raise
            log.warning("briefing_voice_refused", voice=voice)
            voice = None
            narration = await client.speak(chunk, None)
        if narration.audio is None:
            raise ValueError("the voice service returned no audio")
        parts.append(narration.audio)
        used = narration.voice
        if on_part is not None:
            await on_part(len(parts), total)
    return join_wav(parts, GAP_MS), used


def _write(path: Path, data: bytes) -> None:
    """Write next to the target and rename, so a listener never gets half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + _PARTIAL_SUFFIX)
    partial.write_bytes(data)
    os.replace(partial, path)


async def process(briefing_id: uuid.UUID) -> bool:
    """Make one brief. Returns False when there was nothing to do: the request
    was deleted or already handled.

    A `BriefingError` is final and is shown to the reader. Any other exception
    propagates so the queue can retry; the caller records the failure after
    the last attempt.
    """
    async with session_scope() as session:
        row = await session.get(Briefing, briefing_id)
        if row is None or row.status not in ACTIVE_STATUSES:
            return False
        digest = await digest_store.get(session, row.digest_id, full=True)
        if digest is None:
            return False
        view = digest_view(digest)
        voice = row.requested_voice
        row.status, row.progress = STATUS_RUNNING, 0.05

    async def progress(done: int, total: int) -> None:
        await _update(briefing_id, progress=round(0.1 + 0.85 * done / total, 3))

    try:
        if view.audience != "management":
            raise BriefingError(MANAGEMENT_ONLY)
        client = get_voice()
        if client is None:
            raise BriefingError(NO_VOICE)
        script = build_script(view)
        await _update(briefing_id, lines=script.lines, progress=0.1)
        audio, used = await speak(client, script.lines, voice, progress)
    except BriefingError as exc:
        await fail(briefing_id, str(exc))
        return True

    await asyncio.to_thread(_write, audio_path(briefing_id), audio)
    length = duration_ms(audio)
    await _update(
        briefing_id,
        status=STATUS_DONE,
        progress=1.0,
        error=None,
        voice=used,
        duration_ms=length,
        size_bytes=len(audio),
        finished_at=datetime.now(UTC),
    )
    log.info(
        "briefing_done",
        briefing_id=str(briefing_id),
        lines=len(script.lines),
        entries=script.entries,
        estimated_ms=script.estimated_ms,
        duration_ms=length,
        voice=used,
    )
    await purge_files()
    return True


def _stray_files(known: dict[str, str]) -> list[Path]:
    root = media_root()
    if not root.is_dir():
        return []
    now = time.time()
    stray = []
    for path in root.iterdir():
        briefing_id = path.name.removesuffix(_PARTIAL_SUFFIX).removesuffix(".wav")
        if not path.is_file():
            continue
        # The digest or the reader is gone, or the brief was voiced again
        # under a new id. A half-written file, or one written after its row
        # was given up on, is left alone for an hour in case work goes on.
        leftover = path.name.endswith(_PARTIAL_SUFFIX) or known.get(briefing_id) != STATUS_DONE
        if briefing_id not in known or (leftover and now - path.stat().st_mtime > LEFTOVER_SECONDS):
            stray.append(path)
    return stray


async def purge_files() -> int:
    """Delete briefs whose digest or reader is gone, and leftovers of failed work."""
    async with session_scope() as session:
        rows = await session.execute(select(Briefing.id, Briefing.status))
        known = {str(briefing_id): status for briefing_id, status in rows}
    stray = await asyncio.to_thread(_stray_files, known)
    for path in stray:
        await asyncio.to_thread(path.unlink, missing_ok=True)
    return len(stray)
