"""Background tasks. Every task is idempotent: the queue delivers at least once."""

import uuid

from radar.ai.factory import get_embedder
from radar.cache import get_cache
from radar.config import get_settings
from radar.ingest.net import build_client
from radar.ingest.service import embed_pending, enabled_source_ids, ingest_source
from radar.logging import get_logger
from radar.pipeline.runner import run_digest
from radar.worker.brokers import digest_broker, ingest_broker

log = get_logger(__name__)

EMBED_LOCK_TTL = 600
DIGEST_LOCK_TTL = 20 * 60


@ingest_broker.task(task_name="ingest_all", schedule=[{"cron": get_settings().ingest_cron}])
async def ingest_all() -> int:
    """Fan out one fetch task per enabled source."""
    source_ids = await enabled_source_ids()
    for source_id in source_ids:
        await ingest_source_task.kiq(source_id)
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


@digest_broker.task(task_name="build_digest", retry_on_error=True, max_retries=2)
async def build_digest(digest_id: str) -> None:
    """Build a digest, resuming from its last checkpoint after a crash or a retry."""
    async with get_cache().lock(f"digest:{digest_id}", DIGEST_LOCK_TTL) as acquired:
        if not acquired:
            log.info("digest_already_running", digest_id=digest_id)
            return
        await run_digest(uuid.UUID(digest_id))
