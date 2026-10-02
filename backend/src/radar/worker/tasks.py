"""Background tasks. Every task is idempotent: the queue delivers at least once."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from taskiq import Context, TaskiqDepends, TaskiqEvents, TaskiqState

from radar.ai.factory import get_embedder
from radar.auth import service as auth_service
from radar.auth import sessions as auth_sessions
from radar.cache import get_cache
from radar.config import get_settings
from radar.db import session_scope
from radar.events import enabled as events_enabled
from radar.events import writer as event_writer
from radar.images.store import get_image_store
from radar.ingest import avatars
from radar.ingest.detect import DETECT_TTL_SECONDS, NotFound, detect, detect_key, detected_json
from radar.ingest.measure import measure
from radar.ingest.net import build_client
from radar.ingest.service import embed_pending, enabled_source_ids, ingest_source
from radar.logging import get_logger
from radar.pipeline.runner import report_failure, run_digest
from radar.publishing import service as publishing_service
from radar.ranker import train as ranker_train
from radar.recsys import adaptation as recsys_adaptation
from radar.recsys import service as recsys_service
from radar.resume import service as resume_service
from radar.shorts import service as shorts_service
from radar.shorts.renderer import RendererBusy
from radar.store import digests as digest_store
from radar.store import profiles as profile_store
from radar.store import schedules as schedule_store
from radar.vulns import kev
from radar.worker.brokers import (
    DIGEST_IDLE_TIMEOUT_MS,
    MEDIA_IDLE_TIMEOUT_MS,
    PROFILE_IDLE_TIMEOUT_MS,
    digest_broker,
    ingest_broker,
    media_broker,
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
# Adapting asks the model to name at most NAMING_PER_RUN new interests, each
# bounded by the model timeout; the lock outlives that.
ADAPT_LOCK_TTL = 600
SHORT_LOCK_TTL = MEDIA_IDLE_TIMEOUT_MS // 1000 - 60
SHORT_RUN_LIMIT = SHORT_LOCK_TTL - 30
SHORT_ATTEMPTS = 2
# A redelivered task resumes a video after the idle timeout and may run for
# nearly as long again; only after that is the video given up on.
STALE_SHORT_AFTER = timedelta(milliseconds=2 * MEDIA_IDLE_TIMEOUT_MS)
# Writing a post is one model call and a page fetch for the picture.
POST_LOCK_TTL = 300
# The event writer runs every minute and stops before the next run is due.
EVENTS_WRITE_BUDGET = 45.0
# Loading a month of events and fitting takes minutes at most.
RANKER_LOCK_TTL = 3600


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


@ingest_broker.task(task_name="detect_source")
async def detect_source_task(request_id: str, address: str, selector: str | None = None) -> None:
    """What an address is and how to read it, for the api that waits on the
    answer: it runs here, where the browser is (ingest/detect.py)."""
    result: dict[str, object]
    async with build_client() as client:
        try:
            found = await detect(address, client, selector)
            result = {"ok": True, "found": detected_json(found)}
        except NotFound as exc:
            result = {"ok": False, "error": str(exc)}
        except Exception as exc:
            log.warning("detect_failed", address=address[:200], error=type(exc).__name__)
            result = {"ok": False, "error": "Не удалось проверить адрес. Попробуйте ещё раз."}
    await get_cache().set_json(detect_key(request_id), result, ttl=DETECT_TTL_SECONDS)


@ingest_broker.task(task_name="measure_articles")
async def measure_articles(article_ids: list[int]) -> int:
    """Read the pages of articles a reader sees, for their reading time."""
    return await measure(article_ids)


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


@profile_broker.task(task_name="adapt_profiles", retry_on_error=True, max_retries=2)
async def adapt_profiles(user_id: str) -> bool:
    """Let the reader's adaptive profiles learn from their marks and what they saw.

    Queued after marks and batches of impressions; bursts collapse into a few
    runs the same way as refresh_taste.
    """
    cache = get_cache()
    dirty = f"adapt-dirty:{user_id}"
    async with cache.lock(f"adapt:{user_id}", ADAPT_LOCK_TTL) as acquired:
        if not acquired:
            await cache.set_json(dirty, 1, ADAPT_LOCK_TTL)
            return False
        for _ in range(TASTE_MAX_ROUNDS):
            await cache.delete(dirty)
            await recsys_adaptation.adapt_reader(uuid.UUID(user_id), cache=cache)
            if await cache.get_json(dirty) is None:
                break
    return True


@media_broker.task(task_name="make_short", retry_on_error=True, max_retries=SHORT_ATTEMPTS)
async def make_short(video_id: str, context: Context = TaskiqDepends()) -> None:
    """Write, voice and render the short video of a digest."""
    async with get_cache().lock(f"short:{video_id}", SHORT_LOCK_TTL) as acquired:
        if not acquired:
            return
        try:
            async with asyncio.timeout(SHORT_RUN_LIMIT):
                await shorts_service.process(uuid.UUID(video_id))
        except Exception as exc:
            attempt = int(context.message.labels.get("_retries", 0)) + 1
            log.warning(
                "short_attempt_failed", video_id=video_id, attempt=attempt, error=type(exc).__name__
            )
            if attempt >= SHORT_ATTEMPTS:
                message = (
                    "Видеосервис занят. Попробуйте через несколько минут."
                    if isinstance(exc, RendererBusy)
                    else shorts_service.GENERIC_FAILURE
                )
                await shorts_service.fail(uuid.UUID(video_id), message)
            raise


@media_broker.task(task_name="purge_short_files")
async def purge_short_files() -> int:
    """Delete video files whose digest or reader is gone. Runs on the media
    worker, the only one that can write to the media volume."""
    removed = await shorts_service.purge_files()
    if removed:
        log.info("short_files_purged", count=removed)
    return removed


@media_broker.task(task_name="refresh_short_voices")
async def refresh_short_voices() -> int:
    """Pass the voice service's list of voices on to the api through the cache.
    The media worker is the only role that can reach the voice service."""
    voices = await shorts_service.refresh_voices(get_cache())
    return len(voices)


@media_broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _voices_at_start(state: TaskiqState) -> None:
    # Readers get the voice choice as soon as the worker is up, not after the
    # next housekeeping round. The voice service may still be starting; the
    # next round fills the list in then.
    try:
        await shorts_service.refresh_voices(get_cache())
    except Exception as exc:
        log.warning("short_voices_not_refreshed", error=type(exc).__name__)


@ingest_broker.task(task_name="refresh_kev", schedule=[{"cron": "7 * * * *"}])
async def refresh_kev() -> int:
    """Every hour: the CISA catalogue of exploited vulnerabilities, if it changed."""
    url = get_settings().kev_url
    if not url:
        return 0
    async with build_client() as client, session_scope() as session:
        kept, last_modified = await kev.refresh(session, client, get_cache(), url)
    # Remembered after the commit: a failed one must not turn the next round into a 304.
    await kev.remember(get_cache(), last_modified)
    return kept


@ingest_broker.task(task_name="refresh_source_avatars", schedule=[{"cron": "41 */6 * * *"}])
async def refresh_source_avatars() -> int:
    """Every six hours: pictures for sources that have none yet, a few dozen at a time."""
    async with build_client() as client, session_scope() as session:
        return await avatars.refresh_avatars(session, client, get_image_store())


@ingest_broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _kev_at_start(state: TaskiqState) -> None:
    # A fresh stack looks vulnerabilities up before the first hourly round,
    # and shows its sources' pictures before the first six-hourly one.
    for task, event in (
        (refresh_kev, "kev_not_refreshed"),
        (refresh_source_avatars, "avatars_not_refreshed"),
    ):
        try:
            await task()
        except Exception as exc:
            log.warning(event, error=f"{type(exc).__name__}: {exc}"[:300])


@ingest_broker.task(task_name="housekeeping", schedule=[{"cron": "*/10 * * * *"}])
async def housekeeping() -> dict[str, int]:
    """Give up on resumes and videos no worker finished, drop expired sessions
    and delete guest accounts that have lived their day."""
    now = datetime.now(UTC)
    settings = get_settings()
    async with session_scope() as session:
        resumes = await resume_service.fail_stale(session, now - STALE_RESUME_AFTER)
        shorts = await shorts_service.fail_stale(session, now - STALE_SHORT_AFTER)
        sessions = await auth_sessions.purge_expired(session)
        guests = await auth_service.purge_guests(
            session, now - timedelta(hours=settings.guest_ttl_hours)
        )
        impressions = await profile_store.purge_impressions(
            session, now - timedelta(days=recsys_adaptation.SCOPE_DAYS)
        )
    if resumes or shorts:
        log.warning("stale_work_failed", resumes=resumes, shorts=shorts)
    # Deleted guests and digests leave their video files behind.
    if settings.shorts_url:
        try:
            await purge_short_files.kiq()
            if settings.tts_url:
                await refresh_short_voices.kiq()
        except Exception as exc:
            log.warning("short_purge_not_queued", error=type(exc).__name__)
    return {
        "resumes": resumes,
        "shorts": shorts,
        "sessions": sessions,
        "guests": guests,
        "impressions": impressions,
    }


@ingest_broker.task(task_name="run_digest_schedules", schedule=[{"cron": "* * * * *"}])
async def run_digest_schedules() -> int:
    """Every minute: start the digests readers scheduled for now."""
    async with session_scope() as session:
        started = await schedule_store.start_due(
            session, datetime.now(UTC), max_active_total=get_settings().max_active_digests
        )
    for digest_id in started:
        try:
            await build_digest.kiq(str(digest_id))
        except Exception:
            log.exception("scheduled_digest_not_queued", digest_id=str(digest_id))
            async with session_scope() as session:
                await digest_store.mark_failed(session, digest_id, "Очередь задач недоступна.")
    return len(started)


@ingest_broker.task(task_name="write_events", schedule=[{"cron": "* * * * *"}])
async def write_events() -> int:
    """Every minute: take the events waiting in Valkey into ClickHouse and
    delete those of deleted accounts."""
    return await event_writer.flush(budget_seconds=EVENTS_WRITE_BUDGET)


@ingest_broker.task(task_name="train_ranker", schedule=[{"cron": get_settings().ranker_train_cron}])
async def train_ranker() -> str:
    """Every night: train the feed ranker on the events and switch it on or off."""
    if not events_enabled():
        return "events off"
    async with get_cache().lock("ranker-train", RANKER_LOCK_TTL) as acquired:
        if not acquired:
            return "locked"
        run = await ranker_train.train()
    return run.status


@ingest_broker.task(task_name="plan_posts", schedule=[{"cron": "* * * * *"}])
async def plan_posts() -> dict[str, int]:
    """Every minute: create the posts whose slots are due, send the ones whose
    time has come, take over the ones a dead worker left behind."""
    created = await publishing_service.plan()
    stuck = await publishing_service.recover()
    ready = await publishing_service.due()
    for post_id in [*created, *stuck["compose"]]:
        await compose_post.kiq(str(post_id))
    for post_id in ready:
        await send_post.kiq(str(post_id))
    return {
        "planned": len(created),
        "sending": len(ready),
        "interrupted": len(stuck["interrupted"]),
    }


@digest_broker.task(task_name="compose_post", retry_on_error=True, max_retries=2)
async def compose_post(post_id: str) -> str:
    """Write a planned post. Runs where the model is: it is model work."""
    async with get_cache().lock(f"post:{post_id}", POST_LOCK_TTL) as acquired:
        if not acquired:
            return "locked"
        return await publishing_service.compose(uuid.UUID(post_id), get_cache())


@ingest_broker.task(task_name="send_post")
async def send_post(post_id: str) -> str:
    """Publish one post; a failure is recorded on the post, not retried here."""
    async with get_cache().lock(f"post:{post_id}", POST_LOCK_TTL) as acquired:
        if not acquired:
            return "locked"
        return await publishing_service.send(uuid.UUID(post_id))
