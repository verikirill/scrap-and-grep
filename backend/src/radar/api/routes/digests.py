"""Digests: creation, progress stream, exports and comparison."""

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.sse import EventSourceResponse, ServerSentEvent
from sqlalchemy import select

from radar.api.deps import CacheDep, CurrentUser, SessionDep, SettingsDep, user_rate_limit
from radar.api.reading import measure_soon
from radar.api.schemas import CompareOut, DigestCreate, InterestChange, ScoreChange
from radar.db import session_scope
from radar.db.models import Digest, Profile
from radar.domain import ProfileSpec
from radar.logging import get_logger
from radar.pipeline.runner import events_channel
from radar.render.docx import render_docx
from radar.render.markdown import render_markdown
from radar.store import digests as digest_store
from radar.views import DigestSummaryView, DigestView, digest_summary, digest_view
from radar.worker.tasks import build_digest, purge_short_files

router = APIRouter(tags=["digests"])
log = get_logger(__name__)

_digest_limit = Depends(
    user_rate_limit("digest", lambda settings: settings.digest_rate_limit_per_minute)
)
# Builds one reader may have in flight. The total is capped separately
# (max_active_digests), this keeps a single account from taking every slot.

EXPORT_TTL_SECONDS = 24 * 3600
STATUS_POLL_SECONDS = 5
HEARTBEAT_SECONDS = 15
STREAM_LIMIT_SECONDS = 30 * 60
MAX_STREAMS_PER_USER = 8
DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_TERMINAL = {digest_store.STATUS_DONE, digest_store.STATUS_FAILED}


async def _load(
    session: SessionDep, user: CurrentUser, digest_id: uuid.UUID, *, full: bool = False
) -> Digest:
    """The reader's own digest; someone else's is reported as missing."""
    digest = await digest_store.get(session, digest_id, user_id=user.id, full=full)
    if digest is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Дайджест не найден.")
    return digest


async def _load_done(session: SessionDep, user: CurrentUser, digest_id: uuid.UUID) -> DigestView:
    digest = await _load(session, user, digest_id, full=True)
    if digest.status != digest_store.STATUS_DONE:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Дайджест ещё не готов.")
    return digest_view(digest)


@router.post("/digests", status_code=status.HTTP_202_ACCEPTED, dependencies=[_digest_limit])
async def create_digest(
    payload: DigestCreate, session: SessionDep, settings: SettingsDep, user: CurrentUser
) -> DigestSummaryView:
    """Register a digest and queue its build. Progress is at /digests/{id}/events."""
    profile = (
        await session.execute(
            select(Profile).where(Profile.id == payload.profile_id, Profile.user_id == user.id)
        )
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Профиль не найден.")
    if (
        await digest_store.count_active(session, user.id) >= digest_store.MAX_ACTIVE_PER_USER
        or await digest_store.count_active(session) >= settings.max_active_digests
    ):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Уже собирается несколько выпусков. Дождитесь их завершения.",
            headers={"Retry-After": "30"},
        )
    end = payload.period_end or datetime.now(UTC)
    start = payload.period_start or end - timedelta(days=payload.period_days or 7)
    digest = await digest_store.create(
        session,
        user_id=user.id,
        profile_id=profile.id,
        profile=ProfileSpec.model_validate(profile.spec),
        profile_version=profile.version,
        period_start=start,
        period_end=end,
    )
    # The worker must find the row, so commit before the task is queued.
    await session.commit()
    try:
        await build_digest.kiq(str(digest.id))
    except Exception as exc:
        log.exception("digest_enqueue_failed", digest_id=str(digest.id))
        await digest_store.mark_failed(session, digest.id, "Очередь задач недоступна.")
        await session.commit()
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="Очередь задач недоступна."
        ) from exc
    await session.refresh(digest)
    return digest_summary(digest)


@router.get("/digests")
async def list_digests(
    session: SessionDep,
    user: CurrentUser,
    profile_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> list[DigestSummaryView]:
    digests = await digest_store.list_recent(session, user.id, profile_id, limit)
    return [digest_summary(digest) for digest in digests]


@router.get("/digests/compare")
async def compare_digests(
    base: uuid.UUID, other: uuid.UUID, session: SessionDep, user: CurrentUser
) -> CompareOut:
    """What changed between two digests, article by article and interest by interest."""
    base_view = await _load_done(session, user, base)
    other_view = await _load_done(session, user, other)
    base_items = {item.article_id: item for topic in base_view.topics for item in topic.items}
    other_items = {item.article_id: item for topic in other_view.topics for item in topic.items}
    kept = [
        ScoreChange(
            item=item,
            base_score=base_items[article_id].score,
            delta=round(item.score - base_items[article_id].score, 3),
        )
        for article_id, item in other_items.items()
        if article_id in base_items
    ]
    return CompareOut(
        base_id=base,
        other_id=other,
        added=[item for article_id, item in other_items.items() if article_id not in base_items],
        removed=[item for article_id, item in base_items.items() if article_id not in other_items],
        kept=sorted(kept, key=lambda change: -abs(change.delta)),
        interest_changes=_interest_changes(base_view.profile, other_view.profile),
        settings_changed=_settings_changed(base_view.profile, other_view.profile),
    )


def _interest_changes(base: ProfileSpec, other: ProfileSpec) -> list[InterestChange]:
    before = {interest.id: interest for interest in base.interests}
    after = {interest.id: interest for interest in other.interests}
    changes = [
        InterestChange(id=key, title=after[key].title, change="added")
        for key in after
        if key not in before
    ]
    changes += [
        InterestChange(id=key, title=before[key].title, change="removed")
        for key in before
        if key not in after
    ]
    changes += [
        InterestChange(id=key, title=after[key].title, change="changed")
        for key in after
        if key in before and after[key] != before[key]
    ]
    return changes


def _settings_changed(base: ProfileSpec, other: ProfileSpec) -> list[str]:
    fields = ("role", "exclusions", "min_score", "max_items", "languages", "categories")
    return [field for field in fields if getattr(base, field) != getattr(other, field)]


@router.get("/digests/{digest_id}")
async def get_digest(digest_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> DigestView:
    view = digest_view(await _load(session, user, digest_id, full=True))
    await measure_soon(
        item.article_id
        for topic in view.topics
        for item in topic.items
        if item.reading_minutes is None
    )
    return view


@router.delete(
    "/digests/{digest_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_digest_limit]
)
async def delete_digest(
    digest_id: uuid.UUID,
    session: SessionDep,
    cache: CacheDep,
    settings: SettingsDep,
    user: CurrentUser,
) -> Response:
    await session.delete(await _load(session, user, digest_id))
    await session.commit()
    await cache.delete(f"export:{digest_id}:md", f"export:{digest_id}:docx")
    # The video row went with the digest; its file is removed by the media
    # worker, the only one that may write to the media volume.
    if settings.shorts_url:
        try:
            await purge_short_files.kiq()
        except Exception as exc:
            log.warning("short_purge_not_queued", error=type(exc).__name__)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _attachment(view: DigestView, extension: str) -> dict[str, str]:
    name = f"digest-{view.period_end:%Y-%m-%d}-{view.id.hex[-6:]}.{extension}"
    return {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"}


@router.get("/digests/{digest_id}/export.md")
async def export_markdown(
    digest_id: uuid.UUID, session: SessionDep, cache: CacheDep, user: CurrentUser
) -> Response:
    view = await _load_done(session, user, digest_id)
    key = f"export:{digest_id}:md"
    body = await cache.get_bytes(key)
    if body is None:
        body = (await asyncio.to_thread(render_markdown, view)).encode("utf-8")
        await cache.set_bytes(key, body, EXPORT_TTL_SECONDS)
    return Response(
        body, media_type="text/markdown; charset=utf-8", headers=_attachment(view, "md")
    )


@router.get("/digests/{digest_id}/export.docx")
async def export_docx(
    digest_id: uuid.UUID, session: SessionDep, cache: CacheDep, user: CurrentUser
) -> Response:
    view = await _load_done(session, user, digest_id)
    key = f"export:{digest_id}:docx"
    body = await cache.get_bytes(key)
    if body is None:
        body = await asyncio.to_thread(render_docx, view)
        await cache.set_bytes(key, body, EXPORT_TTL_SECONDS)
    return Response(body, media_type=DOCX_MEDIA_TYPE, headers=_attachment(view, "docx"))


async def _status_event(digest_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, Any] | None:
    async with session_scope() as session:
        digest = await digest_store.get(session, digest_id, user_id=user_id)
    if digest is None:
        return None
    return {
        "status": digest.status,
        "stage": digest.stage,
        "progress": digest.progress,
        "error": digest.error,
    }


@router.get("/digests/{digest_id}/events", response_class=EventSourceResponse)
async def digest_events(
    digest_id: uuid.UUID, cache: CacheDep, user: CurrentUser
) -> AsyncIterator[ServerSentEvent]:
    """Live build progress over Server-Sent Events.

    Any api replica can serve the stream: workers publish to Valkey, not to a
    particular process. The row in PostgreSQL is re-read every few seconds, so
    a client that connects late or misses a message still sees the final state.
    """
    # Ownership is checked before subscribing: the channel name is derived
    # from the id, and progress of someone else's build is not ours to relay.
    if await _status_event(digest_id, user.id) is None:
        yield ServerSentEvent(event="error", data={"detail": "Дайджест не найден."})
        return
    # Each open stream holds a subscription and polls the database; a reader
    # needs a couple, not hundreds. The counter expires on its own if a
    # replica dies without decrementing it.
    streams = f"sse:{user.id}"
    if (await cache.incr(streams, ttl=STREAM_LIMIT_SECONDS + 60) or 0) > MAX_STREAMS_PER_USER:
        await cache.decr(streams)
        yield ServerSentEvent(event="error", data={"detail": "Открыто слишком много вкладок."})
        return
    stream = cache.subscribe(events_channel(digest_id))
    try:
        # Subscribe before the first read, otherwise a "done" published in
        # between would be lost.
        await anext(stream)
        current = await _status_event(digest_id, user.id)
        if current is None:
            yield ServerSentEvent(event="error", data={"detail": "Дайджест не найден."})
            return
        yield ServerSentEvent(event="progress", data=current)
        if current["status"] in _TERMINAL:
            return

        started = last_poll = last_beat = time.monotonic()
        async for message in stream:
            now = time.monotonic()
            if message is not None:
                yield ServerSentEvent(event="progress", data=message)
                if message.get("status") in _TERMINAL:
                    return
                last_beat = now
            if now - last_poll >= STATUS_POLL_SECONDS:
                last_poll = now
                current = await _status_event(digest_id, user.id)
                if current is None or current["status"] in _TERMINAL:
                    if current is not None:
                        yield ServerSentEvent(event="progress", data=current)
                    return
            if now - last_beat >= HEARTBEAT_SECONDS:
                last_beat = now
                yield ServerSentEvent(comment="keep-alive")
            if now - started >= STREAM_LIMIT_SECONDS:
                return
    finally:
        await stream.aclose()
        await cache.decr(streams)
