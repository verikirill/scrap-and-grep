"""Operational commands: migrations, seeding, one-off ingestion and digests."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from importlib import resources
from pathlib import Path
from typing import Annotated

import typer
from alembic import command
from alembic.config import Config
from sqlalchemy import select

from radar import aio
from radar.config import get_settings
from radar.logging import configure_logging, get_logger

app = typer.Typer(no_args_is_help=True, add_completion=False)
log = get_logger("radar.cli")


@app.callback()
def _configure() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, json=settings.log_json)


def _alembic_config() -> Config:
    config = Config()
    config.set_main_option("script_location", str(resources.files("radar") / "migrations"))
    return config


async def _setup_checkpoints() -> None:
    from radar.pipeline.runner import checkpointer

    async with checkpointer() as saver:
        await saver.setup()


def _existing(path: Path | None) -> Path | None:
    """A missing snapshot is not an error: the stack then starts with live feeds only."""
    return path if path is not None and path.exists() else None


async def _seed(sample: Path | None) -> None:
    from radar.db import session_scope
    from radar.seed import import_articles, seed_defaults

    async with session_scope() as session:
        added = await seed_defaults(session)
    log.info("seed_done", **added)
    if sample is not None:
        async with session_scope() as session:
            count = await import_articles(session, sample)
        log.info("sample_imported", path=str(sample), articles=count)


async def _queue_first_ingest() -> None:
    """Ask the workers to fetch every source now instead of at the next cron tick.

    Best effort: if the broker is not reachable yet, the scheduler picks the
    work up on its own a few minutes later.
    """
    from radar.worker.brokers import ingest_broker
    from radar.worker.tasks import ingest_all

    try:
        await ingest_broker.startup()
        await ingest_all.kiq()
        await ingest_broker.shutdown()
    except Exception as exc:
        log.warning("first_ingest_not_queued", error=f"{type(exc).__name__}: {exc}"[:200])
    else:
        log.info("first_ingest_queued")


async def _bootstrap(seed: bool, sample: Path | None, ingest: bool) -> None:
    await _setup_checkpoints()
    if seed:
        await _seed(sample)
    if ingest:
        await _queue_first_ingest()


@app.command()
def migrate(
    seed: Annotated[bool, typer.Option(help="Insert default sources and profiles.")] = False,
    sample: Annotated[Path | None, typer.Option(help="JSONL snapshot to import.")] = None,
    ingest: Annotated[bool, typer.Option(help="Queue an immediate fetch of all sources.")] = False,
) -> None:
    """Apply schema migrations and create LangGraph checkpoint tables."""
    command.upgrade(_alembic_config(), "head")
    aio.run(_bootstrap(seed, _existing(sample), ingest))


@app.command()
def seed(
    sample: Annotated[Path | None, typer.Option(help="JSONL snapshot to import.")] = None,
) -> None:
    """Insert default sources and profiles, optionally with sample articles."""
    aio.run(_seed(_existing(sample)))


@app.command()
def ingest(
    source: Annotated[str | None, typer.Option(help="Source slug; all enabled if omitted.")] = None,
) -> None:
    """Fetch feeds now, in this process, and embed what is new."""

    async def run() -> None:
        from radar.ai.factory import get_embedder
        from radar.cache import get_cache
        from radar.db import session_scope
        from radar.db.models import Source
        from radar.ingest.net import build_client
        from radar.ingest.service import embed_pending, enabled_source_ids, ingest_source

        if source is None:
            source_ids = await enabled_source_ids()
        else:
            async with session_scope() as session:
                found = await session.scalar(select(Source.id).where(Source.slug == source))
            if found is None:
                raise typer.BadParameter(f"unknown source: {source}")
            source_ids = [found]

        slots = asyncio.Semaphore(6)
        async with build_client() as client:

            async def one(source_id: int) -> int:
                async with slots:
                    return (await ingest_source(source_id, client, get_cache())).new_articles

            counts = await asyncio.gather(*(one(source_id) for source_id in source_ids))
        embedded = await embed_pending(get_embedder())
        typer.echo(f"sources={len(source_ids)} new_articles={sum(counts)} embedded={embedded}")

    aio.run(run())


@app.command()
def embed() -> None:
    """Embed articles that have no vector for the active model."""

    async def run() -> None:
        from radar.ai.factory import get_embedder
        from radar.ingest.service import embed_pending

        typer.echo(f"embedded={await embed_pending(get_embedder(), max_articles=100_000)}")

    aio.run(run())


@app.command()
def digest(
    profile: Annotated[str, typer.Option(help="Profile name (exact match).")],
    email: Annotated[
        str | None, typer.Option(help="Owner of the profile; the demo account if omitted.")
    ] = None,
    days: Annotated[int, typer.Option(min=1, max=90)] = 7,
    out: Annotated[Path, typer.Option(help="Directory for the .md and .docx files.")] = Path("."),
) -> None:
    """Build a digest in this process and write it as Markdown and DOCX."""

    async def run() -> None:
        from radar.auth import DEMO_EMAIL
        from radar.db import session_scope
        from radar.db.models import Profile, User
        from radar.domain import ProfileSpec
        from radar.pipeline.runner import report_failure, run_digest
        from radar.render.docx import render_docx
        from radar.render.markdown import render_markdown
        from radar.store import digests as digest_store
        from radar.views import digest_view

        now = datetime.now(UTC)
        async with session_scope() as session:
            row = await session.scalar(
                select(Profile)
                .join(User, User.id == Profile.user_id)
                .where(Profile.name == profile, User.email == (email or DEMO_EMAIL).lower())
            )
            if row is None:
                raise typer.BadParameter(f"unknown profile: {profile}")
            created = await digest_store.create(
                session,
                user_id=row.user_id,
                profile_id=row.id,
                profile=ProfileSpec.model_validate(row.spec),
                profile_version=row.version,
                period_start=now - timedelta(days=days),
                period_end=now,
            )
            digest_id: uuid.UUID = created.id

        try:
            await run_digest(digest_id)
        except Exception as exc:
            # No queue here, so no retry: record the failure before leaving.
            await report_failure(digest_id, exc)
            raise
        async with session_scope() as session:
            loaded = await digest_store.get(session, digest_id, full=True)
            if loaded is None:
                raise typer.Exit(code=1)
            view = digest_view(loaded)
        out.mkdir(parents=True, exist_ok=True)
        stem = f"digest-{now:%Y%m%d}-{digest_id.hex[-6:]}"
        (out / f"{stem}.md").write_text(render_markdown(view), encoding="utf-8", newline="\n")
        (out / f"{stem}.docx").write_bytes(render_docx(view))
        typer.echo(f"digest={digest_id} items={view.stats.get('selected')} -> {out / stem}.md")

    aio.run(run())


@app.command("grant-admin")
def grant_admin(
    email: str,
    revoke: Annotated[bool, typer.Option(help="Take the role away instead.")] = False,
) -> None:
    """Let an account manage the source catalogue, or stop it from doing so.

    The role is granted here, by someone with access to the server, never by
    registering with a particular address.
    """

    async def run() -> None:
        from radar.auth.service import set_admin
        from radar.db import session_scope

        async with session_scope() as session:
            found = await set_admin(session, email, is_admin=not revoke)
        if not found:
            raise typer.BadParameter(f"no registered account {email}")
        typer.echo(f"{email}: {'not ' if revoke else ''}admin")

    aio.run(run())


@app.command("export-articles")
def export_articles_command(
    path: Path,
    days: Annotated[int | None, typer.Option(help="Only articles newer than this.")] = None,
    content_limit: Annotated[
        int | None, typer.Option(help="Trim full text to this many characters.")
    ] = None,
) -> None:
    """Dump stored articles to JSONL (the format `migrate --sample` reads)."""

    async def run() -> None:
        from radar.db import session_scope
        from radar.seed import export_articles

        since = datetime.now(UTC) - timedelta(days=days) if days else None
        async with session_scope() as session:
            count = await export_articles(session, path, since, content_limit)
        typer.echo(f"exported={count}")

    aio.run(run())


if __name__ == "__main__":
    app()


@app.command("telegram-mock")
def telegram_mock(
    host: str = typer.Option("127.0.0.1", help="Address to listen on."),
    port: int = typer.Option(8089, help="Port to listen on."),
) -> None:
    """Run a stand-in for the Telegram Bot API, with a viewer of what was sent."""
    import uvicorn

    from radar.publishing.mock_api import app as mock_app

    uvicorn.run(mock_app, host=host, port=port, log_level="warning")
