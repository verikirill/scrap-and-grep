"""Digest persistence: lifecycle, results and loading for the API."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from radar.db.models import Digest, DigestItem, DigestTopic
from radar.domain import DigestOverview, GradedCandidate, ProfileSpec, Topic

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_FAILED = "failed"


async def create(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    profile_id: uuid.UUID | None,
    profile: ProfileSpec,
    profile_version: int,
    period_start: datetime,
    period_end: datetime,
) -> Digest:
    digest = Digest(
        user_id=user_id,
        profile_id=profile_id,
        profile_spec=profile.model_dump(mode="json"),
        profile_version=profile_version,
        period_start=period_start,
        period_end=period_end,
        status=STATUS_QUEUED,
    )
    session.add(digest)
    await session.flush()
    return digest


async def get(
    session: AsyncSession,
    digest_id: uuid.UUID,
    *,
    user_id: uuid.UUID | None = None,
    full: bool = False,
) -> Digest | None:
    """Load a digest. With `user_id` only that reader's digest is returned;
    workers, which act on behalf of the system, leave it out."""
    statement = select(Digest).where(Digest.id == digest_id)
    if user_id is not None:
        statement = statement.where(Digest.user_id == user_id)
    if full:
        statement = statement.options(selectinload(Digest.topics), selectinload(Digest.items))
    return (await session.execute(statement)).scalar_one_or_none()


async def list_recent(
    session: AsyncSession, user_id: uuid.UUID, profile_id: uuid.UUID | None, limit: int
) -> list[Digest]:
    statement = (
        select(Digest)
        .where(Digest.user_id == user_id)
        .order_by(Digest.created_at.desc())
        .limit(limit)
    )
    if profile_id is not None:
        statement = statement.where(Digest.profile_id == profile_id)
    return list((await session.execute(statement)).scalars().all())


async def set_progress(
    session: AsyncSession, digest_id: uuid.UUID, *, stage: str, progress: float
) -> None:
    # Progress events are written while the graph keeps running, so the last
    # one can land after the result is saved. A finished digest stays finished.
    await session.execute(
        update(Digest)
        .where(Digest.id == digest_id, Digest.status != STATUS_DONE)
        .values(
            status=STATUS_RUNNING,
            stage=stage,
            progress=progress,
            error=None,
            finished_at=None,
            heartbeat_at=datetime.now(UTC),
        )
    )


async def count_active(session: AsyncSession, user_id: uuid.UUID | None = None) -> int:
    """Builds queued or running, for everyone or for one reader."""
    statement = (
        select(func.count())
        .select_from(Digest)
        .where(Digest.status.in_([STATUS_QUEUED, STATUS_RUNNING]))
    )
    if user_id is not None:
        statement = statement.where(Digest.user_id == user_id)
    return int(await session.scalar(statement) or 0)


async def fail_stale(session: AsyncSession, older_than: datetime) -> int:
    """Mark digests that never finished as failed, so the UI stops waiting.

    Covers the cases the queue cannot: a task lost before it was acknowledged
    by any worker, or a worker that dies on every attempt. Age is measured
    from the last progress report, so a long but live build is left alone.
    """
    result = await session.execute(
        update(Digest)
        .where(
            Digest.status.in_([STATUS_QUEUED, STATUS_RUNNING]),
            func.coalesce(Digest.heartbeat_at, Digest.created_at) < older_than,
        )
        .values(
            status=STATUS_FAILED,
            error="Сборка не завершилась за отведённое время.",
            finished_at=datetime.now(UTC),
        )
        .returning(Digest.id)
    )
    return len(result.all())


async def mark_failed(session: AsyncSession, digest_id: uuid.UUID, error: str) -> None:
    await session.execute(
        update(Digest)
        .where(Digest.id == digest_id)
        .values(status=STATUS_FAILED, error=error[:2000], finished_at=datetime.now(UTC))
    )


async def save_result(
    session: AsyncSession,
    digest_id: uuid.UUID,
    *,
    overview: DigestOverview,
    topics: Sequence[Topic],
    graded: Sequence[GradedCandidate],
    rejected: dict[int, str],
    stats: dict[str, Any],
) -> None:
    """Replace the digest contents in one transaction.

    Deleting first makes the write idempotent: a redelivered task or a resumed
    graph run ends with exactly one copy of the result.
    """
    # Lock the digest row: two workers finishing the same build (a redelivered
    # task racing the original) must write one after the other, not interleave.
    locked = await session.scalar(select(Digest.id).where(Digest.id == digest_id).with_for_update())
    if locked is None:
        # Deleted by the user while it was being built. Nothing to save.
        return
    await session.execute(delete(DigestItem).where(DigestItem.digest_id == digest_id))
    await session.execute(delete(DigestTopic).where(DigestTopic.digest_id == digest_id))

    selected_ids: set[int] = set()
    position = 0
    for topic_position, topic in enumerate(topics):
        row = DigestTopic(
            digest_id=digest_id, position=topic_position, title=topic.title, overview=topic.overview
        )
        session.add(row)
        await session.flush()
        for item in topic.items:
            graded_item = item.graded
            selected_ids.add(item.article.id)
            session.add(
                DigestItem(
                    digest_id=digest_id,
                    topic_id=row.id,
                    article_id=item.article.id,
                    position=position,
                    selected=True,
                    score=graded_item.score,
                    retrieval_score=graded_item.candidate.retrieval_score,
                    personal=graded_item.personal,
                    personal_note=graded_item.personal_note,
                    relevance=graded_item.grade.relevance,
                    interest_id=graded_item.interest_id,
                    reason=graded_item.grade.reason,
                    headline=item.text.headline if item.text else item.article.title,
                    summary=item.text.summary if item.text else "",
                    why=item.text.why if item.text else "",
                    duplicates=[dup.model_dump() for dup in item.duplicates],
                )
            )
            position += 1

    for graded_item in graded:
        if graded_item.article.id in selected_ids:
            continue
        session.add(
            DigestItem(
                digest_id=digest_id,
                article_id=graded_item.article.id,
                position=position,
                selected=False,
                score=graded_item.score,
                retrieval_score=graded_item.candidate.retrieval_score,
                personal=graded_item.personal,
                personal_note=graded_item.personal_note,
                relevance=graded_item.grade.relevance,
                interest_id=graded_item.interest_id,
                reason=graded_item.grade.reason,
                reject_reason=rejected.get(graded_item.article.id, "low_score"),
            )
        )
        position += 1

    await session.execute(
        update(Digest)
        .where(Digest.id == digest_id)
        .values(
            status=STATUS_DONE,
            stage="done",
            progress=1.0,
            error=None,
            title=overview.title,
            highlights=list(overview.highlights),
            stats=stats,
            finished_at=datetime.now(UTC),
        )
    )
