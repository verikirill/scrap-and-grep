"""Resume upload and the profile suggested from it."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from radar.api.deps import CacheDep, CurrentUser, SessionDep, SettingsDep, user_rate_limit
from radar.api.uploads import read_limited
from radar.domain import ProfileSpec
from radar.logging import get_logger
from radar.recsys.service import forget_taste
from radar.resume import service
from radar.resume.files import BUILTIN_FORMATS, DOCLING_FORMATS, detect_format
from radar.resume.model import ResumeError, ResumeFacts
from radar.worker.tasks import process_resume, refresh_taste

router = APIRouter(prefix="/resume", tags=["resume"])
log = get_logger(__name__)

_upload_limit = Depends(
    user_rate_limit("resume", lambda settings: settings.resume_rate_limit_per_minute)
)


class ResumeOut(BaseModel):
    status: str
    error: str | None
    file_format: str
    size_bytes: int
    parser: str | None
    facts: ResumeFacts | None
    suggestion: ProfileSpec | None
    created_at: datetime
    processed_at: datetime | None


def _out(row: Any) -> ResumeOut:
    return ResumeOut(
        status=row.status,
        error=row.error,
        file_format=row.file_format,
        size_bytes=row.size_bytes,
        parser=row.parser,
        facts=ResumeFacts.model_validate(row.facts) if row.facts else None,
        suggestion=ProfileSpec.model_validate(row.suggestion) if row.suggestion else None,
        created_at=row.created_at,
        processed_at=row.processed_at,
    )


@router.post("", status_code=status.HTTP_202_ACCEPTED, dependencies=[_upload_limit])
async def upload_resume(
    request: Request, user: CurrentUser, session: SessionDep, settings: SettingsDep
) -> ResumeOut:
    """Accept a resume as the raw request body and queue its analysis.

    The file name arrives in the `X-File-Name` header and is used only to tell
    text formats apart; it is not stored.
    """
    limit = settings.resume_max_bytes
    data = await read_limited(
        request, limit, f"Размер файла превышает {limit // 1_000_000} МБ. Выберите файл поменьше."
    )
    try:
        file_format = detect_format(data, request.headers.get("x-file-name", "")[:200])
    except ResumeError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc
    accepted = DOCLING_FORMATS if settings.docparser_url else (*BUILTIN_FORMATS, "html")
    if file_format not in accepted:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Для формата {file_format.upper()} требуется сервис Docling. "
                "Загрузите файл в PDF, DOCX или TXT."
            ),
        )
    row = await service.accept(session, user.id, data=data, file_format=file_format)
    # The worker must find the row, so commit before the task is queued.
    await session.commit()
    try:
        await process_resume.kiq(str(user.id), row.created_at.isoformat())
    except Exception as exc:
        log.exception("resume_enqueue_failed", user_id=str(user.id))
        await service.fail(user.id, row.created_at, "Очередь задач недоступна. Попробуйте позже.")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="Очередь задач недоступна."
        ) from exc
    return _out(row)


@router.get("")
async def get_resume(user: CurrentUser, session: SessionDep) -> ResumeOut | None:
    """The reader's resume and what was learned from it, or `null` if there is none."""
    row = await service.get(session, user.id)
    return _out(row) if row is not None else None


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(user: CurrentUser, session: SessionDep, cache: CacheDep) -> Response:
    """Forget everything learned from the resume."""
    if await service.remove(session, user.id):
        await session.commit()
        await forget_taste(cache, user.id)
        try:
            await refresh_taste.kiq(str(user.id))
        except Exception as exc:
            log.warning("taste_refresh_not_queued", error=type(exc).__name__)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
