"""Structured logging shared by the API, workers and the CLI."""

import logging
import re
import sys

import structlog

_SHARE_TOKEN = re.compile(r"(/shared-profiles/)[A-Za-z0-9_-]+")


class _HideShareTokens(logging.Filter):
    """Replaces share-link tokens in uvicorn's access lines with a placeholder."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(
                _SHARE_TOKEN.sub(lambda match: match.group(1) + "…", arg)
                if isinstance(arg, str)
                else arg
                for arg in record.args
            )
        return True


def configure_logging(level: str = "INFO", *, json: bool = True) -> None:
    shared: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer(ensure_ascii=False)
        if json
        else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[*shared, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level.upper())),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
    # Third-party libraries still use stdlib logging; keep them quiet but visible.
    logging.basicConfig(level=logging.WARNING, stream=sys.stdout, format="%(message)s")
    # httpx logs every request URL at INFO, and a Bot API URL carries the bot's
    # token: this stays at WARNING whatever the root level becomes.
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
    # The access log writes every path, and a profile link carries its token
    # in the path.
    logging.getLogger("uvicorn.access").addFilter(_HideShareTokens())


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]
