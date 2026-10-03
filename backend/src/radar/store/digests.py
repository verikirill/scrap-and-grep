"""Digest persistence: lifecycle, results and loading for the API."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from radar.cards import priority
from radar.db.models import Article, Digest, DigestItem, DigestTopic
from radar.digest_extras import (
    HISTORY_DAYS,
    HISTORY_ISSUES,
    changes,
    tag_counts,
    vulnerability_states,
)
from radar.domain import DigestOverview, GradedCandidate, ItemSummary, ProfileSpec, Topic

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
    origin: str = "manual",
) -> Digest:
    digest = Digest(
        user_id=user_id,
        profile_id=profile_id,
        profile_spec=profile.model_dump(mode="json"),
        profile_version=profile_version,
        period_start=period_start,
        period_end=period_end,
        status=STATUS_QUEUED,
        origin=origin,
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


# A reader may have this many digests in the making at once, by hand or by schedule.
MAX_ACTIVE_PER_USER = 3


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
    # A finished digest stays finished: a failure after the save (a retry
    # that ran out, for instance) must not hide a good result.
    await session.execute(
        update(Digest)
        .where(Digest.id == digest_id, Digest.status != STATUS_DONE)
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
                    kind=graded_item.grade.kind,
                    priority=priority(graded_item.grade.kind, item.text),
                    card=_card(item.text),
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
                kind=graded_item.grade.kind,
            )
        )
        position += 1

    stats = {**stats, **await _history(session, digest_id, topics)}
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
            implications=list(overview.implications),
            stats=stats,
            finished_at=datetime.now(UTC),
        )
    )


async def _history(
    session: AsyncSession, digest_id: uuid.UUID, topics: Sequence[Topic]
) -> dict[str, Any]:
    """What the earlier issues of the same profile and audience say about this
    one: what changed for the vulnerabilities they had, and the previous issue
    of the same length's tags, for management's numbers."""
    digest = await session.get(Digest, digest_id)
    if digest is None or digest.profile_id is None:
        return {}
    audience = digest.profile_spec.get("audience", "specialist")
    found = await session.scalars(
        select(Digest)
        .where(
            Digest.profile_id == digest.profile_id,
            Digest.status == STATUS_DONE,
            Digest.id != digest_id,
            Digest.created_at < digest.created_at,
            Digest.created_at >= digest.created_at - timedelta(days=HISTORY_DAYS),
        )
        .order_by(Digest.created_at.desc())
        # One build for both audiences writes two digests of one profile.
        .limit(HISTORY_ISSUES * 2)
    )
    earlier = [row for row in found if row.profile_spec.get("audience", "specialist") == audience]
    earlier = earlier[:HISTORY_ISSUES]
    if not earlier:
        return {}
    rows = (
        await session.execute(
            select(DigestItem, Article.url, Article.title)
            .join(Article, Article.id == DigestItem.article_id)
            .where(DigestItem.digest_id.in_([row.id for row in earlier]), DigestItem.selected)
        )
    ).all()
    when = {row.id: row.finished_at or row.created_at for row in earlier}
    texts = [
        (
            ItemSummary.model_validate({"summary": item.summary, **(item.card or {})}),
            item,
            url,
            title,
        )
        for item, url, title in rows
    ]
    past = vulnerability_states(
        (text, item.headline or title, url, when[item.digest_id])
        for text, item, url, title in texts
    )
    current = vulnerability_states(
        (item.text, item.text.headline or item.article.title, item.article.url, digest.created_at)
        for topic in topics
        for item in topic.items
        if item.text is not None
    )
    result: dict[str, Any] = {
        "changes": [change.model_dump(mode="json") for change in changes(past, current)]
    }
    length = digest.period_end - digest.period_start
    previous = next(
        (
            row
            for row in earlier
            if abs((row.period_end - row.period_start) - length) < timedelta(hours=1)
        ),
        None,
    )
    if previous is not None:
        result["tags_before"] = tag_counts(
            text for text, item, _, _ in texts if item.digest_id == previous.id
        )
    return result


def _card(text: ItemSummary | None) -> dict[str, Any]:
    """The card part of an entry, as stored with it."""
    if text is None:
        return {}
    return text.model_dump(
        mode="json", include={"attack", "vulnerability", "tags", "unsupported", "references"}
    )
