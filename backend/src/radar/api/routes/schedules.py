"""Digests built on a schedule: each profile may have one."""

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from radar.api.deps import CurrentUser, SessionDep, user_rate_limit
from radar.api.routes.profiles import get_owned
from radar.db.models import DigestSchedule
from radar.digest_schedule import ScheduleError, validate
from radar.store import schedules as schedule_store

router = APIRouter(tags=["schedules"])

_write_limit = Depends(user_rate_limit("write", lambda settings: settings.rate_limit_per_minute))


class ScheduleIn(BaseModel):
    cadence: Literal["daily", "weekdays", "weekly"]
    # Monday is 0; for a weekly schedule only.
    weekday: int | None = Field(default=None, ge=0, le=6)
    # The reader's local time, HH:MM.
    time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    # An IANA zone such as Europe/Moscow, from the reader's browser.
    timezone: str = Field(min_length=1, max_length=64)


class ScheduleOut(BaseModel):
    profile_id: uuid.UUID
    cadence: str
    weekday: int | None
    time: str
    timezone: str
    next_run_at: datetime
    last_run_at: datetime | None
    last_digest_id: uuid.UUID | None


def _out(schedule: DigestSchedule) -> ScheduleOut:
    hours, minutes = divmod(schedule.minute_of_day, 60)
    return ScheduleOut(
        profile_id=schedule.profile_id,
        cadence=schedule.cadence,
        weekday=schedule.weekday,
        time=f"{hours:02d}:{minutes:02d}",
        timezone=schedule.timezone,
        next_run_at=schedule.next_run_at,
        last_run_at=schedule.last_run_at,
        last_digest_id=schedule.last_digest_id,
    )


@router.get("/digest-schedules")
async def list_schedules(session: SessionDep, user: CurrentUser) -> list[ScheduleOut]:
    return [_out(schedule) for schedule in await schedule_store.for_user(session, user.id)]


@router.put("/profiles/{profile_id}/schedule", dependencies=[_write_limit])
async def put_schedule(
    profile_id: uuid.UUID, payload: ScheduleIn, session: SessionDep, user: CurrentUser
) -> ScheduleOut:
    """Build this profile's digest by itself, at the reader's time."""
    profile = await get_owned(session, user, profile_id)
    hours, minutes = (int(part) for part in payload.time.split(":"))
    try:
        cadence = validate(payload.cadence, payload.weekday, hours * 60 + minutes, payload.timezone)
    except ScheduleError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    schedule = await schedule_store.put(
        session,
        profile,
        cadence=cadence,
        weekday=payload.weekday,
        minute_of_day=hours * 60 + minutes,
        timezone=payload.timezone,
        now=datetime.now(UTC),
    )
    await session.commit()
    return _out(schedule)


@router.delete(
    "/profiles/{profile_id}/schedule",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[_write_limit],
)
async def delete_schedule(
    profile_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> Response:
    await get_owned(session, user, profile_id)
    await schedule_store.remove(session, profile_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
