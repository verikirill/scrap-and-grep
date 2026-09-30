"""Health probes, runtime metadata and metrics."""

from importlib.metadata import version

from fastapi import APIRouter, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import func, select, text

from radar.ai.factory import get_embedder
from radar.api.deps import CacheDep, SessionDep, SettingsDep
from radar.api.schemas import MetaOut
from radar.db.models import Source
from radar.resume.files import BUILTIN_FORMATS, DOCLING_FORMATS
from radar.resume.parse import PARSER_BUILTIN, PARSER_DOCLING
from radar.store.articles import corpus_stats

router = APIRouter(tags=["system"])

# A source is reported as failing after this many consecutive errors.
FAILING_AFTER = 3


@router.get("/health/live", include_in_schema=False)
async def live() -> dict[str, str]:
    """The process is up. Used by the container healthcheck."""
    return {"status": "ok"}


@router.get("/health/ready", include_in_schema=False)
async def ready(session: SessionDep, cache: CacheDep, response: Response) -> dict[str, str]:
    """The process can serve requests: PostgreSQL answers. Valkey is reported
    but does not fail readiness, because the API degrades without it."""
    checks = {"database": "ok", "cache": "ok" if await cache.ping() else "down"}
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        checks["database"] = "down"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return checks


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/api/v1/meta")
async def meta(session: SessionDep, settings: SettingsDep) -> MetaOut:
    embedder = get_embedder()
    stats = await corpus_stats(session, embedder.model_id)
    sources = await session.scalar(select(func.count()).select_from(Source))
    failing = await session.scalar(
        select(func.count())
        .select_from(Source)
        .where(Source.enabled, Source.consecutive_failures >= FAILING_AFTER)
    )
    return MetaOut(
        version=version("radar"),
        embedding_provider=settings.embedding_provider,
        embedding_model=embedder.model_id,
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model if settings.llm_provider == "ollama" else "heuristic",
        articles=stats["articles"],
        articles_last_day=stats["last_day"],
        embedded=stats["embedded"],
        oldest_article=stats["oldest"],
        newest_article=stats["newest"],
        sources=int(sources or 0),
        sources_failing=int(failing or 0),
        demo_login=settings.demo_login,
        registration_open=settings.registration_open,
        resume_parser=PARSER_DOCLING if settings.docparser_url else PARSER_BUILTIN,
        resume_formats=list(
            DOCLING_FORMATS if settings.docparser_url else (*BUILTIN_FORMATS, "html")
        ),
        resume_max_bytes=settings.resume_max_bytes,
    )
