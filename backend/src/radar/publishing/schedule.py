"""When a channel posts: the slots of a day in the channel's time zone.

Slots are computed, not stored. A post row carries the slot it fills, and a
unique index on (channel, slot) makes planning idempotent: the planner runs
every minute and may see the same slot many times.
"""

import hashlib
from datetime import UTC, date, datetime, time, timedelta

from radar.publishing.settings import DigestPost, Schedule, minutes_of

# A slot missed by more than this (the stack was down) is skipped, not
# posted late: a pile of stale posts at once is worse than a gap.
GRACE = timedelta(minutes=20)


def _jitter(key: str, local: datetime, minutes: int) -> timedelta:
    if minutes == 0:
        return timedelta()
    digest = hashlib.sha256(f"{key}:{local.isoformat()}".encode()).digest()
    shift = int.from_bytes(digest[:4], "big") % (2 * minutes + 1) - minutes
    return timedelta(minutes=shift)


def _clocks(schedule: Schedule) -> list[int]:
    """Minutes after midnight of the day's slots, before jitter."""
    if schedule.mode == "times":
        return [minutes_of(clock) for clock in schedule.times]
    start, end = minutes_of(schedule.window_start), minutes_of(schedule.window_end)
    return list(range(start, end + 1, schedule.every_minutes))


def slots_on(day: date, schedule: Schedule, key: str) -> list[datetime]:
    """The slots of one local day, in UTC, at most `max_per_day` of them."""
    if day.weekday() not in schedule.days:
        return []
    zone = schedule.zone
    slots = []
    for minute in _clocks(schedule)[: schedule.max_per_day]:
        local = datetime.combine(day, time(minute // 60, minute % 60), tzinfo=zone)
        shifted = local + _jitter(key, local, schedule.jitter_minutes)
        # Jitter never moves a slot into another day.
        if shifted.date() != day:
            shifted = local
        slots.append(shifted.astimezone(UTC))
    return slots


def slots_between(start: datetime, end: datetime, schedule: Schedule, key: str) -> list[datetime]:
    """Every slot in [start, end), in order."""
    zone = schedule.zone
    day = start.astimezone(zone).date() - timedelta(days=1)
    last = end.astimezone(zone).date() + timedelta(days=1)
    found: list[datetime] = []
    while day <= last:
        found.extend(slot for slot in slots_on(day, schedule, key) if start <= slot < end)
        day += timedelta(days=1)
    return sorted(found)


def slots_to_prepare(now: datetime, schedule: Schedule, key: str) -> list[datetime]:
    """Slots whose post should exist by now: due within `prepare_minutes`,
    not missed by more than the grace period."""
    ahead = timedelta(minutes=schedule.prepare_minutes)
    return slots_between(now - GRACE, now + ahead, schedule, key)


def next_slot(now: datetime, schedule: Schedule, key: str) -> datetime | None:
    """The first slot after now within two weeks; None if the schedule is empty."""
    upcoming = slots_between(now, now + timedelta(days=14), schedule, key)
    return upcoming[0] if upcoming else None


def digest_slot(now: datetime, digest: DigestPost, schedule: Schedule) -> datetime | None:
    """This week's round-up slot if it should be prepared now, else None."""
    if not digest.enabled:
        return None
    zone = schedule.zone
    local_now = now.astimezone(zone)
    day = local_now.date() - timedelta(days=(local_now.weekday() - digest.weekday) % 7)
    minute = minutes_of(digest.time)
    slot = datetime.combine(day, time(minute // 60, minute % 60), tzinfo=zone).astimezone(UTC)
    ahead = timedelta(minutes=schedule.prepare_minutes)
    return slot if now - GRACE <= slot < now + ahead else None
