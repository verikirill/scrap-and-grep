"""Operational commands: migrations, seeding, one-off ingestion and digests."""

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
from alembic import command
from alembic.config import Config
from sqlalchemy import select

from radar import aio
from radar.config import get_settings
from radar.console import (
    Audience,
    ConsoleError,
    Target,
    addresses,
    file_stem,
    moment,
    period_text,
    progress_line,
    targets,
)
from radar.logging import configure_logging, get_logger

if TYPE_CHECKING:
    from radar.views import DigestView

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


async def _migrate_events() -> None:
    """The events schema in ClickHouse. Not fatal: until it is there only the
    events wait in their stream, and the writer applies the schema itself as
    soon as the server answers."""
    from radar.events import clickhouse, enabled

    if not enabled():
        return
    try:
        await clickhouse.migrate()
    except Exception as exc:
        log.warning("clickhouse_not_migrated", error=f"{type(exc).__name__}: {exc}"[:200])


async def _bootstrap(seed: bool, sample: Path | None, ingest: bool) -> None:
    await _setup_checkpoints()
    await _migrate_events()
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
    """Apply schema migrations, create LangGraph checkpoint tables and the
    events schema in ClickHouse."""
    command.upgrade(_alembic_config(), "head")
    aio.run(_bootstrap(seed, _existing(sample), ingest))


@app.command()
def seed(
    sample: Annotated[Path | None, typer.Option(help="JSONL snapshot to import.")] = None,
) -> None:
    """Insert default sources and profiles, optionally with sample articles."""
    aio.run(_seed(_existing(sample)))


async def _ingest_now(source: str | None = None) -> tuple[int, int, int]:
    """Fetch the sources in this process and embed what is new: sources, new
    articles, embedded."""
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
    return len(source_ids), sum(counts), embedded


@app.command()
def ingest(
    source: Annotated[str | None, typer.Option(help="Source slug; all enabled if omitted.")] = None,
) -> None:
    """Fetch feeds now, in this process, and embed what is new."""
    sources, new_articles, embedded = aio.run(_ingest_now(source))
    typer.echo(f"sources={sources} new_articles={new_articles} embedded={embedded}")


@app.command()
def embed() -> None:
    """Embed articles that have no vector for the active model."""

    async def run() -> None:
        from radar.ai.factory import get_embedder
        from radar.ingest.service import embed_pending

        typer.echo(f"embedded={await embed_pending(get_embedder(), max_articles=100_000)}")

    aio.run(run())


PROGRESS_POLL_SECONDS = 1.0


async def _add_sources(path: Path) -> None:
    """Each address of the file detected, added to the catalog and fetched now,
    as «Любой адрес» does in the browser. One that cannot be read is reported
    and skipped; one already in the catalog is fetched as it is."""
    from radar.ai.factory import get_embedder
    from radar.cache import get_cache
    from radar.db import session_scope
    from radar.db.models import Source
    from radar.ingest.detect import NotFound, as_source, detect
    from radar.ingest.net import build_client
    from radar.ingest.service import embed_pending, ingest_source

    wanted = addresses(await asyncio.to_thread(path.read_text, encoding="utf-8"))
    typer.echo(f"Источники из {path.name}: {len(wanted)}")
    async with build_client() as client:
        for address in wanted:
            try:
                found = await detect(address, client)
            except NotFound as exc:
                typer.echo(f"  - {address}: {exc}")
                continue
            source = as_source(found)
            async with session_scope() as session:
                known = await session.scalar(
                    select(Source.id).where(
                        (Source.slug == source.slug) | (Source.feed_url == source.feed_url)
                    )
                )
                if known is None:
                    session.add(source)
                    await session.flush()
                    known = source.id
            outcome = await ingest_source(known, client, get_cache())
            how = found.fetch_method or "plain"
            typer.echo(
                f"  + {found.name} ({found.kind}, {how}): новых публикаций {outcome.new_articles}"
            )
    await embed_pending(get_embedder())


async def _register(target: Target, email: str | None) -> tuple[uuid.UUID, datetime, datetime]:
    """The digest's row for this target, and the start and end of its period."""
    from radar.auth import DEMO_EMAIL
    from radar.db import session_scope
    from radar.db.models import Profile, User
    from radar.domain import ProfileSpec
    from radar.store import digests as digest_store

    now = datetime.now(UTC)
    owner = (email or DEMO_EMAIL).lower()
    async with session_scope() as session:
        if target.spec is not None:
            user_id = await session.scalar(select(User.id).where(User.email == owner))
            if user_id is None:
                raise typer.BadParameter(f"no account {owner}: run `radar migrate --seed` first")
            spec, profile_id, version = target.spec, None, 1
        else:
            row = await session.scalar(
                select(Profile)
                .join(User, User.id == Profile.user_id)
                .where(Profile.name == target.profile_name, User.email == owner)
            )
            if row is None:
                raise typer.BadParameter(f"unknown profile: {target.profile_name}")
            user_id, profile_id, version = row.user_id, row.id, row.version
            spec = ProfileSpec.model_validate(row.spec)
        start, end = target.bounds(spec.audience, now)
        created = await digest_store.create(
            session,
            user_id=user_id,
            profile_id=profile_id,
            profile=spec,
            profile_version=version,
            period_start=start,
            period_end=end,
        )
        return created.id, start, end


async def _show_progress(digest_id: uuid.UUID) -> None:
    """Print each stage as the build reaches it, read from the digest's row."""
    from radar.db import session_scope
    from radar.db.models import Digest

    shown = None
    while True:
        async with session_scope() as session:
            row = (
                await session.execute(
                    select(Digest.stage, Digest.progress).where(Digest.id == digest_id)
                )
            ).one_or_none()
        if row is not None and row.stage not in (shown, "done"):
            shown = row.stage
            typer.echo(progress_line(row.stage, row.progress))
        await asyncio.sleep(PROGRESS_POLL_SECONDS)


def _hand_over(path: Path) -> None:
    """Run as root to write into any ./out, the file goes to the folder's owner."""
    if sys.platform != "win32" and os.geteuid() == 0:
        owner = path.parent.stat()
        os.chown(path, owner.st_uid, owner.st_gid)


def _write(out: Path, stem: str, markdown: str, docx: bytes) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    md_path, docx_path = out / f"{stem}.md", out / f"{stem}.docx"
    md_path.write_text(markdown, encoding="utf-8", newline="\n")
    docx_path.write_bytes(docx)
    for path in (md_path, docx_path):
        _hand_over(path)
    return md_path


async def _build(target: Target, email: str | None, out: Path, mail_to: str | None = None) -> Path:
    from radar.db import session_scope
    from radar.pipeline.runner import report_failure, run_digest
    from radar.render.docx import render_docx
    from radar.render.markdown import render_markdown
    from radar.store import digests as digest_store
    from radar.views import digest_view

    digest_id, start, end = await _register(target, email)
    typer.echo(f"\n{target.label}: выпуск за {period_text(start, end)}")
    watcher = asyncio.create_task(_show_progress(digest_id))
    try:
        await run_digest(digest_id)
    except Exception as exc:
        # No queue here, so no retry: record the failure before leaving.
        await report_failure(digest_id, exc)
        raise
    finally:
        watcher.cancel()
    async with session_scope() as session:
        loaded = await digest_store.get(session, digest_id, full=True)
        if loaded is None:
            raise typer.Exit(code=1)
        view = digest_view(loaded)
    stem = file_stem(target.label, start, end, datetime.now().astimezone())
    markdown = await asyncio.to_thread(_write, out, stem, render_markdown(view), render_docx(view))
    stats = view.stats
    typer.echo(
        f"Готово: {stats.get('selected', 0)} записей из {stats.get('window_total', 0)} "
        f"публикаций, модель {stats.get('llm')}, {stats.get('duration_seconds', 0):.0f} с"
    )
    if mail_to:
        await _mail(view, mail_to)
    return markdown


def _moment(text: str) -> datetime:
    """`moment` for an option: typer shows a ValueError as the value alone,
    without the words that say what is wrong with it."""
    try:
        return moment(text)
    except ConsoleError as exc:
        raise typer.BadParameter(str(exc)) from exc


async def _mail(view: DigestView, to: str) -> None:
    from radar import mail

    settings = get_settings()
    if not settings.smtp_host:
        raise typer.BadParameter(
            "почта не настроена: задайте RADAR_SMTP_HOST", param_hint="--mail-to"
        )
    try:
        await mail.send(mail.letter(view, to, settings), settings)
    except mail.MailError as exc:
        raise typer.BadParameter(str(exc), param_hint="--mail-to") from exc
    typer.echo(f"Отправлен на {to}")


@app.command()
def digest(
    audience: Annotated[
        Audience | None,
        typer.Option(help="The example profile of an audience; both if nothing is chosen."),
    ] = None,
    profile: Annotated[
        str | None, typer.Option(help="A saved profile by name, instead of an audience.")
    ] = None,
    profile_file: Annotated[
        Path | None,
        typer.Option(help="A profile from a JSON file, as in examples/profiles/.", dir_okay=False),
    ] = None,
    email: Annotated[
        str | None, typer.Option(help="Owner of the profile; the demo account if omitted.")
    ] = None,
    days: Annotated[
        int | None,
        typer.Option(
            min=1,
            max=90,
            help="Days of the period, counted back from its end; a day for specialists, "
            "a week for management.",
        ),
    ] = None,
    period_end: Annotated[
        datetime | None,
        typer.Option(
            parser=_moment,
            metavar="<datetime>",
            help="End of the period in ISO 8601, such as 2026-10-03T04:27, Moscow time unless "
            "an offset is given. Now if omitted; a past moment rebuilds a digest of that time "
            "from the stored articles.",
        ),
    ] = None,
    period_start: Annotated[
        datetime | None,
        typer.Option(
            parser=_moment,
            metavar="<datetime>",
            help="Start of the period, written the same way, instead of --days.",
        ),
    ] = None,
    fresh: Annotated[bool, typer.Option(help="Fetch every source before building.")] = False,
    source_file: Annotated[
        Path | None,
        typer.Option(
            "--sources",
            help="A file of addresses to add before building, one per line: sites, news "
            "sections, feeds or @channels.",
            dir_okay=False,
        ),
    ] = None,
    out: Annotated[Path, typer.Option(help="Directory for the .md and .docx files.")] = Path("."),
    mail_to: Annotated[
        str | None,
        typer.Option(help="Also send each digest to this address (RADAR_SMTP_HOST must be set)."),
    ] = None,
) -> None:
    """Build digests in this process and write them as Markdown and DOCX.

    Without options: one for specialists over the last day and one for
    management over the last week, from the example profiles.
    """
    try:
        wanted = targets(audience, profile, profile_file, days, start=period_start, end=period_end)
    except ConsoleError as exc:
        raise typer.BadParameter(str(exc)) from exc

    async def run() -> list[Path]:
        if source_file is not None:
            await _add_sources(source_file)
        if fresh:
            typer.echo("Опрашиваем источники...")
            sources, new_articles, _ = await _ingest_now()
            typer.echo(f"{sources} источников, новых публикаций: {new_articles}")
        return [await _build(target, email, out, mail_to) for target in wanted]

    for path in aio.run(run()):
        typer.echo(f"Markdown: {path}  DOCX: {path.parent / (path.stem + '.docx')}")


@app.command("grant-admin")
def grant_admin(
    email: str,
    revoke: Annotated[bool, typer.Option(help="Take the role away instead.")] = False,
) -> None:
    """Let an account manage the source catalogue and see the analytics, or
    stop it from doing so.

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


@app.command("train-ranker")
def train_ranker() -> None:
    """Train the feed ranker on the events now, as the nightly task does, and
    switch it on only if it beats the hand blend."""

    async def run() -> None:
        from radar.events import enabled
        from radar.ranker.train import train

        if not enabled():
            raise typer.BadParameter("events are off: set RADAR_CLICKHOUSE_URL")
        result = await train()
        typer.echo(f"{result.version}: {result.status}. {result.note}")

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
