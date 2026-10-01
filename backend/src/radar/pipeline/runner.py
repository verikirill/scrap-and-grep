"""Run the digest graph for one digest row and report progress."""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from radar.ai.factory import get_embedder, get_intelligence
from radar.cache import Cache, get_cache
from radar.config import get_settings
from radar.db import session_scope
from radar.events import record
from radar.logging import get_logger
from radar.pipeline.graph import DigestState, build_graph
from radar.pipeline.ports import PipelineDeps
from radar.pipeline.sql_store import CachedQueryEmbedder, SqlPipelineStore
from radar.store import digests as digest_store

log = get_logger(__name__)

# Share of the progress bar each stage owns: (start, width).
_STAGE_SPAN = {
    "prepare": (0.02, 0.08),
    "retrieve": (0.10, 0.08),
    "grade": (0.18, 0.42),
    "select": (0.60, 0.05),
    "summarize": (0.65, 0.25),
    "compose": (0.90, 0.06),
    "persist": (0.96, 0.03),
}


def events_channel(digest_id: uuid.UUID | str) -> str:
    return f"digest:{digest_id}"


async def report_failure(
    digest_id: uuid.UUID, exc: BaseException, cache: Cache | None = None
) -> None:
    """Mark the digest as failed for good and tell the listeners.

    Called once, after the last attempt. The full exception is in the log; the
    reader gets only the kind of failure, because driver messages can name
    internal hosts.
    """
    error = f"Сборка прервалась ({type(exc).__name__}). Подробности в журнале сервиса."
    async with session_scope() as session:
        await digest_store.mark_failed(session, digest_id, error)
    await (cache or get_cache()).publish(
        events_channel(digest_id), {"status": "failed", "error": error}
    )


@asynccontextmanager
async def checkpointer() -> AsyncIterator[AsyncPostgresSaver]:
    """Postgres-backed checkpointer with its own small pool.

    Prepared statements are off so the connection works through PgBouncer in
    transaction mode; autocommit is what the saver's migrations expect.
    """
    async with AsyncConnectionPool(
        get_settings().checkpoint_dsn,
        min_size=1,
        max_size=4,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": None, "row_factory": dict_row},
    ) as pool:
        saver = AsyncPostgresSaver(pool)  # type: ignore[arg-type]
        yield saver


def default_deps() -> PipelineDeps:
    settings = get_settings()
    embedder = get_embedder()
    return PipelineDeps(
        store=SqlPipelineStore(embedder, settings.per_interest_limit),
        embedder=embedder,
        embed_queries=CachedQueryEmbedder(embedder, get_cache()),
        intelligence=get_intelligence(),
        candidate_limit=settings.candidate_limit,
        llm_provider=settings.llm_provider,
    )


class ProgressTracker:
    """Turn node events into one monotonically growing progress value."""

    def __init__(self) -> None:
        self._totals: dict[str, int] = {}
        self._done: dict[str, int] = {}
        self.progress = 0.0

    def update(self, event: dict[str, Any]) -> dict[str, Any]:
        stage = event["stage"]
        if "total" in event:
            self._totals[stage] = event["total"]
            self._done[stage] = 0
        elif "done" in event:
            self._done[stage] = self._done.get(stage, 0) + event["done"]
        start, width = _STAGE_SPAN.get(stage, (self.progress, 0.0))
        total = self._totals.get(stage, 0)
        share = (self._done.get(stage, 0) / total) if total else 0.0
        self.progress = max(self.progress, min(0.99, start + width * share))
        return {
            "stage": stage,
            "progress": round(self.progress, 3),
            "done": self._done.get(stage),
            "total": total or None,
        }


async def run_digest(
    digest_id: uuid.UUID,
    *,
    deps: PipelineDeps | None = None,
    saver: BaseCheckpointSaver[Any] | None = None,
    cache: Cache | None = None,
) -> None:
    """Build one digest. Safe to call again for the same id.

    A finished or failed digest is left alone. An interrupted one resumes from its last
    checkpoint, so grades and summaries already paid for are not recomputed.
    """
    cache = cache or get_cache()
    async with session_scope() as session:
        digest = await digest_store.get(session, digest_id)
        if digest is None:
            log.warning("digest_missing", digest_id=str(digest_id))
            return
        # Done needs no work. Failed is final too: it is set after the last
        # attempt or by the reaper, and a redelivered message must not revive it.
        if digest.status in (digest_store.STATUS_DONE, digest_store.STATUS_FAILED):
            return
        initial: DigestState = {
            "digest_id": str(digest_id),
            "user_id": str(digest.user_id),
            "profile_id": str(digest.profile_id) if digest.profile_id else None,
            "profile": digest.profile_spec,
            "period_start": digest.period_start.isoformat(),
            "period_end": digest.period_end.isoformat(),
        }

    try:
        if saver is not None:
            await _execute(digest_id, initial, deps or default_deps(), saver, cache)
        else:
            async with checkpointer() as pg_saver:
                await _execute(digest_id, initial, deps or default_deps(), pg_saver, cache)
    except Exception:
        log.exception("digest_attempt_failed", digest_id=str(digest_id))
        raise

    await cache.delete(f"export:{digest_id}:md", f"export:{digest_id}:docx")
    await cache.publish(
        events_channel(digest_id), {"status": "done", "stage": "done", "progress": 1.0}
    )
    log.info("digest_done", digest_id=str(digest_id))
    await record.digest_built(digest_id)


async def _execute(
    digest_id: uuid.UUID,
    initial: DigestState,
    deps: PipelineDeps,
    saver: BaseCheckpointSaver[Any],
    cache: Cache,
) -> None:
    graph = build_graph(deps).compile(checkpointer=saver)
    config: Any = {"configurable": {"thread_id": str(digest_id)}, "max_concurrency": 16}
    snapshot = await graph.aget_state(config)
    # `next` is non-empty when a previous attempt stopped mid-graph: resume it.
    # A thread that ran to the end but whose digest is not marked done is
    # stale; starting on top of it would append to its accumulated lists.
    if not snapshot.next and snapshot.values:
        await saver.adelete_thread(str(digest_id))
    graph_input = None if snapshot.next else initial
    log.info(
        "digest_started",
        digest_id=str(digest_id),
        resumed=bool(snapshot.next),
        next_nodes=sorted(set(snapshot.next)),
        # Non-zero when the previous attempt ended with a task failure: those
        # results are kept. After a hard kill the step starts over and the
        # answer cache absorbs the repeated model calls.
        tasks_pending=len(snapshot.tasks),
        tasks_already_done=sum(1 for task in snapshot.tasks if task.result is not None),
    )
    tracker = ProgressTracker()
    last_written = -1.0
    async for part in graph.astream(graph_input, config, stream_mode="custom", version="v2"):
        if part["type"] != "custom":
            continue
        update = tracker.update(part["data"])
        await cache.publish(events_channel(digest_id), {"status": "running", **update})
        # The row is the source of truth for clients that connect late; write
        # it on stage changes and every few percent, not on every event.
        if update["progress"] - last_written >= 0.03:
            last_written = update["progress"]
            async with session_scope() as session:
                await digest_store.set_progress(
                    session, digest_id, stage=update["stage"], progress=update["progress"]
                )
    # The result is in the digest tables now; the checkpoints have done their
    # job. Failing to delete them costs disk space, not correctness.
    try:
        await saver.adelete_thread(str(digest_id))
    except Exception as exc:
        log.warning("checkpoint_cleanup_failed", digest_id=str(digest_id), error=str(exc)[:200])
