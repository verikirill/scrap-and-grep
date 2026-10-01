"""Digests a reader's schedule orders: keeping the schedules, starting the due ones."""

import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from radar.db.models import DigestSchedule, Profile
from radar.digest_schedule import next_run, previous_run
from radar.domain import ProfileSpec
from radar.logging import get_logger
from radar.store import digests as digest_store

log = get_logger(__name__)

# Schedules started per minute: more wait for the next minute.
BATCH = 50
# A reader whose digests are all still building: try again this much later.
RETRY_AFTER = timedelta(minutes=10)
# A digest covers at most what a manual one can (DigestCreate).
LONGEST_PERIOD = timedelta(days=90)


async def for_user(session: AsyncSession, user_id: uuid.UUID) -> Sequence[DigestSchedule]:
    return (
        (await session.execute(select(DigestSchedule).where(DigestSchedule.user_id == user_id)))
        .scalars()
        .all()
    )


async def put(
    session: AsyncSession,
    profile: Profile,
    *,
    cadence: str,
    weekday: int | None,
    minute_of_day: int,
    timezone: str,
    now: datetime,
) -> DigestSchedule:
    """Set the profile's schedule; the next digest is the first slot from now."""
    schedule = await session.get(DigestSchedule, profile.id)
    if schedule is None:
        schedule = DigestSchedule(profile_id=profile.id, user_id=profile.user_id)
        session.add(schedule)
    schedule.cadence = cadence
    schedule.weekday = weekday if cadence == "weekly" else None
    schedule.minute_of_day = minute_of_day
    schedule.timezone = timezone
    schedule.next_run_at = next_run(cadence, schedule.weekday, minute_of_day, timezone, now)
    await session.flush()
    return schedule


async def remove(session: AsyncSession, profile_id: uuid.UUID) -> None:
    await session.execute(delete(DigestSchedule).where(DigestSchedule.profile_id == profile_id))


async def start_due(
    session: AsyncSession, now: datetime, *, max_active_total: int
) -> list[uuid.UUID]:
    """Create the digests whose time has come; return their ids for the build queue.

    Rows are taken with SKIP LOCKED, so two schedulers never start one slot
    twice. A digest covers the news since the previous scheduled one, so
    nothing falls between two runs, even after the service was down. Each
    row is started in a savepoint: one that fails waits and retries, and
    the others of the minute go ahead.
    """
    rows = (
        await session.execute(
            select(DigestSchedule, Profile)
            .join(Profile, Profile.id == DigestSchedule.profile_id)
            .where(DigestSchedule.next_run_at <= now)
            .order_by(DigestSchedule.next_run_at)
            .limit(BATCH)
            .with_for_update(skip_locked=True, of=DigestSchedule)
        )
    ).all()
    started: list[uuid.UUID] = []
    for schedule, profile in rows:
        # Read before the savepoint: after a rollback the row's attributes expire.
        profile_id = schedule.profile_id
        # The first period starts at the slot before the first run; kept on
        # the row, a retry later does not shrink it to the retry's ten minutes.
        basis = schedule.last_run_at or previous_run(
            schedule.cadence,
            schedule.weekday,
            schedule.minute_of_day,
            schedule.timezone,
            schedule.next_run_at,
        )
        try:
            async with session.begin_nested():
                digest_id = await _start(session, schedule, profile, basis, now, max_active_total)
        except Exception:
            log.exception("scheduled_digest_failed", profile_id=str(profile_id))
            digest_id = None
        if digest_id is None:
            schedule.last_run_at = basis
            schedule.next_run_at = now + RETRY_AFTER
            continue
        started.append(digest_id)
    return started


async def _start(
    session: AsyncSession,
    schedule: DigestSchedule,
    profile: Profile,
    basis: datetime,
    now: datetime,
    max_active_total: int,
) -> uuid.UUID | None:
    """Start one schedule's digest, or None when the reader's builds are all busy."""
    # Two schedulers handling two schedules of one reader count one after the other.
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))").bindparams(
            key=f"digests:{schedule.user_id}"
        )
    )
    if (
        await digest_store.count_active(session, schedule.user_id)
        >= digest_store.MAX_ACTIVE_PER_USER
        or await digest_store.count_active(session) >= max_active_total
    ):
        return None
    digest = await digest_store.create(
        session,
        user_id=schedule.user_id,
        profile_id=profile.id,
        profile=ProfileSpec.model_validate(profile.spec),
        profile_version=profile.version,
        period_start=max(basis, now - LONGEST_PERIOD),
        period_end=now,
        origin="schedule",
    )
    schedule.last_run_at = now
    schedule.last_digest_id = digest.id
    # From now, not from the missed slot: a stack that was down for a week
    # makes one digest of the week, not seven.
    schedule.next_run_at = next_run(
        schedule.cadence, schedule.weekday, schedule.minute_of_day, schedule.timezone, now
    )
    return digest.id
