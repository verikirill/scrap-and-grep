"""FastAPI application factory."""

import re
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram
from starlette.routing import Match

from radar.api.routes import (
    auth,
    catalog,
    digests,
    feed,
    profiles,
    publishing,
    resume,
    shorts,
    system,
)
from radar.cache import get_redis
from radar.config import get_settings
from radar.db import get_engine
from radar.logging import configure_logging, get_logger
from radar.worker.brokers import digest_broker, ingest_broker, profile_broker

log = get_logger(__name__)

REQUESTS = Counter("radar_http_requests_total", "HTTP requests", ["method", "route", "status"])
LATENCY = Histogram("radar_http_request_seconds", "HTTP request latency", ["method", "route"])
_UNMETERED = {"/metrics", "/health/live", "/health/ready"}
_REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{8,64}")
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def is_cross_site(request: Request, allowed_origins: list[str]) -> bool:
    """Was a state-changing request sent by another site's page?

    The session lives in a cookie, which the browser attaches to any request
    to this host. `SameSite=Lax` already keeps it off cross-site POSTs; this
    check is the second line. Browsers label every request with
    `Sec-Fetch-Site`, and a client that sends neither that nor `Origin` is not
    a browser, so it cannot be tricked into carrying someone's cookie.
    """
    if request.method in _SAFE_METHODS:
        return False
    origin = request.headers.get("origin")
    # An origin listed in the settings (the Vite dev server) is trusted even
    # though the browser calls it another site.
    if origin is not None and origin in allowed_origins:
        return False
    fetch_site = request.headers.get("sec-fetch-site")
    if fetch_site is not None:
        return fetch_site not in ("same-origin", "none")
    if origin is None:
        return False
    return urlsplit(origin).netloc != request.headers.get("host")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level, json=settings.log_json)
    # The api only publishes tasks; workers consume them.
    await ingest_broker.startup()
    await digest_broker.startup()
    await profile_broker.startup()
    log.info("api_started", embedding=settings.embedding_provider, llm=settings.llm_provider)
    yield
    await profile_broker.shutdown()
    await digest_broker.shutdown()
    await ingest_broker.shutdown()
    await get_redis().aclose()
    await get_engine().dispose()


def _route_template(request: Request) -> str:
    """Path template rather than the concrete path, to keep metric labels bounded."""
    for route in request.app.routes:
        match, _ = route.matches(request.scope)
        if match == Match.FULL:
            return str(getattr(route, "path", request.url.path))
    return "unmatched"


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Радар: дайджесты ИТ и ИБ",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def observe(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        supplied = request.headers.get("x-request-id", "")
        # Echoed into logs and a response header, so accept only a plain token.
        request_id = supplied if _REQUEST_ID.fullmatch(supplied) else uuid.uuid4().hex
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.perf_counter()
        try:
            response: Response
            if is_cross_site(request, settings.cors_origins):
                response = JSONResponse(
                    status_code=403, content={"detail": "Запрос с другого сайта отклонён."}
                )
            else:
                response = await call_next(request)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
        if request.url.path not in _UNMETERED:
            route = _route_template(request)
            REQUESTS.labels(request.method, route, response.status_code).inc()
            LATENCY.labels(request.method, route).observe(time.perf_counter() - started)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Details stay in the log; the client gets a stable, non-revealing message.
        log.exception("unhandled_error", path=request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Внутренняя ошибка сервиса."})

    app.include_router(system.router)
    for router in (
        auth.router,
        catalog.router,
        profiles.router,
        digests.router,
        resume.router,
        shorts.router,
        feed.router,
        publishing.router,
    ):
        app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
