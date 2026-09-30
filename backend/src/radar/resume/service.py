"""Resume lifecycle: accept a file, process it in a worker, keep only the facts."""

import asyncio
import uuid
from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from radar.ai.factory import get_breaker, get_chat
from radar.config import get_settings
from radar.db import session_scope
from radar.db.models import Resume
from radar.logging import get_logger
from radar.resume.extract import (
    HeuristicResumeExtractor,
    ResilientResumeExtractor,
    ResumeExtractor,
)
from radar.resume.model import (
    STATUS_FAILED,
    STATUS_PROCESSING,
    STATUS_READY,
    ResumeError,
)
from radar.resume.parse import parse_document
from radar.resume.scrub import scrub

log = get_logger(__name__)

_GENERIC_FAILURE = "Не удалось обработать файл. Попробуйте ещё раз или загрузите другой формат."


@lru_cache
def get_extractor() -> ResumeExtractor:
    fallback = HeuristicResumeExtractor()
    chat = get_chat()
    if chat is None:
        return fallback

    from radar.resume.extract import OllamaResumeExtractor

    return ResilientResumeExtractor(OllamaResumeExtractor(chat), fallback, get_breaker())


async def accept(
    session: AsyncSession, user_id: uuid.UUID, *, data: bytes, file_format: str
) -> Resume:
    """Store the upload for the worker, replacing whatever was there before."""
    values = {
        "status": STATUS_PROCESSING,
        "error": None,
        "file_format": file_format,
        "size_bytes": len(data),
        "payload": data,
        "parser": None,
        "facts": None,
        "suggestion": None,
        "created_at": datetime.now(UTC),
        "processed_at": None,
    }
    row = (
        await session.execute(
            insert(Resume)
            .values(user_id=user_id, **values)
            .on_conflict_do_update(index_elements=["user_id"], set_=values)
            .returning(Resume)
        )
    ).scalar_one()
    return row


async def get(session: AsyncSession, user_id: uuid.UUID) -> Resume | None:
    return (
        await session.execute(select(Resume).where(Resume.user_id == user_id))
    ).scalar_one_or_none()


async def remove(session: AsyncSession, user_id: uuid.UUID) -> bool:
    result = await session.execute(
        delete(Resume).where(Resume.user_id == user_id).returning(Resume.user_id)
    )
    return result.first() is not None


async def _finish(user_id: uuid.UUID, uploaded_at: datetime, **values: object) -> None:
    """Record the outcome and drop the file, whatever the outcome was.

    The upload time is part of the condition: if the reader replaced the file
    while this one was being processed, the newer upload is left alone.
    """
    async with session_scope() as session:
        await session.execute(
            update(Resume)
            .where(Resume.user_id == user_id, Resume.created_at == uploaded_at)
            .values(payload=None, processed_at=datetime.now(UTC), **values)
        )


async def fail(user_id: uuid.UUID, uploaded_at: datetime, message: str = _GENERIC_FAILURE) -> None:
    await _finish(user_id, uploaded_at, status=STATUS_FAILED, error=message[:500])


async def process(user_id: uuid.UUID, uploaded_at: datetime) -> bool:
    """Parse and analyse one upload. Returns False when there was nothing to do:
    the upload was replaced, deleted or already handled.

    A `ResumeError` is final and is shown to the reader. Any other exception
    propagates so the queue can retry; the caller records the failure after
    the last attempt.
    """
    settings = get_settings()
    async with session_scope() as session:
        row = (
            await session.execute(
                select(Resume).where(Resume.user_id == user_id).options(undefer(Resume.payload))
            )
        ).scalar_one_or_none()
        if (
            row is None
            or row.created_at != uploaded_at
            or row.status != STATUS_PROCESSING
            or row.payload is None
        ):
            return False
        data, file_format = bytes(row.payload), row.file_format

    try:
        parsed = await parse_document(
            data,
            file_format,
            docparser_url=settings.docparser_url,
            request_timeout=settings.docparser_timeout_seconds,
            max_pages=settings.resume_max_pages,
        )
        # Cut before scrubbing: the extractor reads the first pages anyway, and
        # a long file of noise must not keep the worker busy.
        text = await asyncio.to_thread(scrub, parsed.text[: settings.resume_text_limit * 4])
        text = text[: settings.resume_text_limit]
        extraction = await get_extractor().extract(text)
    except ResumeError as exc:
        await fail(user_id, uploaded_at, str(exc))
        log.info("resume_rejected", user_id=str(user_id), file_format=file_format)
        return True

    await _finish(
        user_id,
        uploaded_at,
        status=STATUS_READY,
        error=None,
        parser=parsed.parser,
        facts=extraction.facts.model_dump(mode="json"),
        suggestion=extraction.suggestion.model_dump(mode="json"),
    )
    # Sizes and formats only: nothing from the resume itself goes to the log.
    log.info(
        "resume_processed",
        user_id=str(user_id),
        file_format=file_format,
        parser=parsed.parser,
        text_chars=len(text),
        by_model=extraction.facts.by_model,
        interests=len(extraction.suggestion.interests),
    )
    return True


async def fail_stale(session: AsyncSession, older_than: datetime) -> int:
    """Give up on uploads no worker finished, and delete their files."""
    result = await session.execute(
        update(Resume)
        .where(Resume.status == STATUS_PROCESSING, Resume.created_at < older_than)
        .values(status=STATUS_FAILED, error=_GENERIC_FAILURE, payload=None)
        .returning(Resume.user_id)
    )
    return len(result.all())
