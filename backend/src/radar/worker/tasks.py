"""Background tasks. Every task is idempotent: the queue delivers at least once."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from taskiq import Context, TaskiqDepends

from radar.ai.factory import get_embedder
from radar.auth import service as auth_service
from radar.auth import sessions as auth_sessions
from radar.cache import get_cache
from radar.config import get_settings
from radar.db import session_scope
from radar.ingest.net import build_client
from radar.ingest.service import embed_pending, enabled_source_ids, ingest_source
from radar.logging import get_logger
from radar.pipeline.runner import report_failure, run_digest
from radar.recsys import service as recsys_service
from radar.resume import service as resume_service
from radar.store import digests as digest_store
from radar.worker.brokers import (
    DIGEST_IDLE_TIMEOUT_MS,
    PROFILE_IDLE_TIMEOUT_MS,
    digest_broker,
    ingest_broker,
    profile_broker,
)

log = get_logger(__name__)

EMBED_LOCK_TTL = 600
# The lock must expire before the queue hands the message to another worker.
# If it outlived the idle timeout, the redelivered task would find the digest
# "already running", acknowledge the message and the build would never resume.
DIGEST_LOCK_TTL = DIGEST_IDLE_TIMEOUT_MS // 1000 - 60
DIGEST_RUN_LIMIT = DIGEST_LOCK_TTL - 30
# Total attempts, the first one included (taskiq counts them this way).
DIGEST_ATTEMPTS = 3
STALE_DIGEST_AFTER = timedelta(milliseconds=3 * DIGEST_IDLE_TIMEOUT_MS)
# Same reasoning as for digests: finish or give up before the message can be
# handed to another worker.
RESUME_LOCK_TTL = PROFILE_IDLE_TIMEOUT_MS // 1000 - 60
RESUME_RUN_LIMIT = RESUME_LOCK_TTL - 30
RESUME_ATTEMPTS = 3
STALE_RESUME_AFTER = timedelta(milliseconds=3 * PROFILE_IDLE_TIMEOUT_MS)
TASTE_LOCK_TTL = 60
# Signals that keep arriving during a refresh can hold it for this many rounds.
TASTE_MAX_ROUNDS = 3


@ingest_broker.task(task_name="ingest_all", schedule=[{"cron": get_settings().ingest_cron}])
async def ingest_all() -> int:
    """Fan out one fetch task per enabled source."""
    source_ids = await enabled_source_ids()
    for source_id in source_ids:
        await ingest_source_task.kiq(source_id)
    # Also covers articles that arrived another way: an imported snapshot, or a
    # switch to a different embedding model.
    await embed_pending_task.kiq()
    return len(source_ids)


@ingest_broker.task(task_name="ingest_source", retry_on_error=True, max_retries=2)
async def ingest_source_task(source_id: int) -> dict[str, object]:
    async with build_client() as client:
        report = await ingest_source(source_id, client, get_cache())
    if report.new_articles:
        await embed_pending_task.kiq()
    return {"source_id": source_id, "status": report.status, "new": report.new_articles}


@ingest_broker.task(task_name="embed_pending", retry_on_error=True, max_retries=2)
async def embed_pending_task() -> int:
    """Embed new articles. One run at a time: a second one would redo the same rows."""
    async with get_cache().lock("embed", EMBED_LOCK_TTL) as acquired:
        if not acquired:
            return 0
        done = await embed_pending(get_embedder())
    log.info("embed_done", count=done)
    return done


@ingest_broker.task(task_name="reap_stale_digests", schedule=[{"cron": "*/10 * * * *"}])
async def reap_stale_digests() -> int:
    """Fail digests that have been queued or running for far too long."""
    async with session_scope() as session:
        reaped = await digest_store.fail_stale(session, datetime.now(UTC) - STALE_DIGEST_AFTER)
    if reaped:
        log.warning("stale_digests_failed", count=reaped)
    return reaped


@digest_broker.task(task_name="build_digest", retry_on_error=True, max_retries=DIGEST_ATTEMPTS)
async def build_digest(digest_id: str, context: Context = TaskiqDepends()) -> None:
    """Build a digest, resuming from its last checkpoint after a crash or a retry."""
    async with get_cache().lock(f"digest:{digest_id}", DIGEST_LOCK_TTL) as acquired:
        if not acquired:
            log.info("digest_already_running", digest_id=digest_id)
            return
        try:
            # Stop before the lock expires. Past that point another worker may
            # pick the message up, and two builds of one digest must not overlap.
            async with asyncio.timeout(DIGEST_RUN_LIMIT):
                await run_digest(uuid.UUID(digest_id))
        except Exception as exc:
            attempt = int(context.message.labels.get("_retries", 0)) + 1
            if attempt >= DIGEST_ATTEMPTS:
                await report_failure(uuid.UUID(digest_id), exc)
            else:
                log.warning("digest_will_retry", digest_id=digest_id, attempt=attempt)
            raise


@profile_broker.task(task_name="process_resume", retry_on_error=True, max_retries=RESUME_ATTEMPTS)
async def process_resume(
    user_id: str, uploaded_at: str, context: Context = TaskiqDepends()
) -> None:
    """Parse an uploaded resume and turn it into a suggested profile."""
    owner, stamp = uuid.UUID(user_id), datetime.fromisoformat(uploaded_at)
    cache = get_cache()
    # One lock per upload, not per reader: a newer file must not be turned
    # away because the previous one is still being read.
    async with cache.lock(f"resume:{user_id}:{stamp.timestamp()}", RESUME_LOCK_TTL) as acquired:
        if not acquired:
            return
        try:
            async with asyncio.timeout(RESUME_RUN_LIMIT):
                done = await resume_service.process(owner, stamp)
        except Exception as exc:
            attempt = int(context.message.labels.get("_retries", 0)) + 1
            # The exception text may quote the document, so only its type is logged.
            log.warning(
                "resume_attempt_failed", user_id=user_id, attempt=attempt, error=type(exc).__name__
            )
            if attempt >= RESUME_ATTEMPTS:
                await resume_service.fail(owner, stamp)
                await recsys_service.forget_taste(cache, owner)
            raise
    if not done:
        return
    # The resume is one of the inputs of the reader's taste. The analysis is
    # already saved, so a failure here must not send the task round again.
    await recsys_service.forget_taste(cache, owner)
    try:
        await refresh_taste.kiq(user_id)
    except Exception as exc:
        log.warning("taste_refresh_not_queued", user_id=user_id, error=type(exc).__name__)


@profile_broker.task(task_name="refresh_taste", retry_on_error=True, max_retries=2)
async def refresh_taste(user_id: str) -> bool:
    """Recompute a reader's taste vector, the one used to find readers alike.

    Queued after every signal. A task that finds another one running leaves a
    note and returns; the running one sees the note and goes round again, so
    the last signal is always included and bursts collapse into a few runs.
    """
    cache = get_cache()
    dirty = f"taste-dirty:{user_id}"
    async with cache.lock(f"taste:{user_id}", TASTE_LOCK_TTL) as acquired:
        if not acquired:
            await cache.set_json(dirty, 1, TASTE_LOCK_TTL)
            return False
        for _ in range(TASTE_MAX_ROUNDS):
            await cache.delete(dirty)
            await recsys_service.store_taste_vector(uuid.UUID(user_id))
            if await cache.get_json(dirty) is None:
                break
    return True


@ingest_broker.task(task_name="housekeeping", schedule=[{"cron": "*/10 * * * *"}])
async def housekeeping() -> dict[str, int]:
    """Give up on resumes no worker finished, drop expired sessions and delete
    guest accounts that have lived their day."""
    now = datetime.now(UTC)
    async with session_scope() as session:
        resumes = await resume_service.fail_stale(session, now - STALE_RESUME_AFTER)
        sessions = await auth_sessions.purge_expired(session)
        guests = await auth_service.purge_guests(
            session, now - timedelta(hours=get_settings().guest_ttl_hours)
        )
    if resumes:
        log.warning("stale_resumes_failed", count=resumes)
    return {"resumes": resumes, "sessions": sessions, "guests": guests}
