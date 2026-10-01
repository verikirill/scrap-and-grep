"""Connections to ClickHouse and its schema.

The schema is a numbered list of SQL files in `schema/`, applied in order and
recorded in `schema_migrations`. Every statement is idempotent (IF NOT EXISTS),
so a run that stopped halfway can simply be repeated. Statements end with a
semicolon at the end of a line; comments stand on lines of their own.
"""

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib import resources
from urllib.parse import urlsplit

import clickhouse_connect
from clickhouse_connect.driver.asyncclient import AsyncClient

from radar.config import get_settings
from radar.logging import get_logger

log = get_logger(__name__)

_CONNECT_TIMEOUT = 5
_QUERY_TIMEOUT = 120
_STATEMENT_END = re.compile(r";\s*(?:\n|$)")
_NAME = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


@asynccontextmanager
async def connect(*, database: str | None = None) -> AsyncIterator[AsyncClient]:
    """A client for the configured server. `database` overrides the configured one."""
    settings = get_settings()
    url = urlsplit(settings.clickhouse_url)
    secure = url.scheme == "https"
    password = settings.clickhouse_password
    client = await clickhouse_connect.get_async_client(
        host=url.hostname or "localhost",
        port=url.port or (8443 if secure else 8123),
        secure=secure,
        username=settings.clickhouse_user,
        password=password.get_secret_value() if password else "",
        database=database or settings.clickhouse_database,
        connect_timeout=_CONNECT_TIMEOUT,
        send_receive_timeout=_QUERY_TIMEOUT,
        client_name="radar",
        # No server session: the analytics page runs its queries side by side,
        # and a session takes one query at a time.
        autogenerate_session_id=False,
    )
    try:
        yield client
    finally:
        await client.close()


def statements(sql: str) -> list[str]:
    lines = [line for line in sql.splitlines() if not line.lstrip().startswith("--")]
    return [part.strip() for part in _STATEMENT_END.split("\n".join(lines)) if part.strip()]


def _files() -> list[tuple[int, str, str]]:
    found = []
    for entry in (resources.files("radar.events") / "schema").iterdir():
        match = _NAME.match(entry.name)
        if match:
            found.append((int(match.group(1)), entry.name, entry.read_text(encoding="utf-8")))
    return sorted(found)


async def migrate() -> list[str]:
    """Create the database and apply the files not applied yet. Returns their names."""
    database = get_settings().clickhouse_database
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", database):
        raise ValueError("RADAR_CLICKHOUSE_DATABASE must be a plain identifier")
    async with connect(database="default") as client:
        await client.command(f"CREATE DATABASE IF NOT EXISTS {database}")
    applied: list[str] = []
    async with connect() as client:
        await client.command(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version UInt32, name String, applied_at DateTime DEFAULT now()) "
            "ENGINE = MergeTree ORDER BY version"
        )
        done = {
            row[0]
            for row in (await client.query("SELECT version FROM schema_migrations")).result_rows
        }
        for version, name, sql in _files():
            if version in done:
                continue
            for statement in statements(sql):
                await client.command(statement)
            await client.insert(
                "schema_migrations", [(version, name)], column_names=["version", "name"]
            )
            applied.append(name)
    if applied:
        log.info("clickhouse_migrated", files=applied)
    return applied
