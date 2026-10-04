# ruff: noqa: F811  (the fixtures are imported from the other tests)
"""How the sources are doing: every poll kept, errors by kind, the sources
that fail and those silent longer than usual."""

import ssl
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from radar.ingest.fetch import Blocked
from radar.ingest.health import error_kind
from radar.ingest.net import UnresolvableHostError, UnsafeUrlError
from radar.ingest.pages import MarkupChanged
from tests.test_accounts_api import api, client, database  # noqa: F401


def _status(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://site.example/feed")
    return httpx.HTTPStatusError(
        "x", request=request, response=httpx.Response(code, request=request)
    )


@pytest.mark.parametrize(
    ("exc", "kind"),
    [
        (UnresolvableHostError("cannot resolve host gone.example"), "dns"),
        (UnsafeUrlError("host resolves to a non-public address"), "unsafe"),
        (Blocked("https://site.example", [("plain", "403"), ("impersonate", "403")]), "refused"),
        (Blocked("https://site.example", [("plain", "503, заглушка Cloudflare")]), "stub"),
        (MarkupChanged("no article links"), "markup"),
        (ValueError("not a feed: <unknown>:2:0: not well-formed"), "markup"),
        (_status(403), "refused"),
        (_status(502), "http"),
        (httpx.ReadTimeout("timed out"), "timeout"),
        (ssl.SSLCertVerificationError("certificate verify failed"), "tls"),
        (httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed"), "tls"),
        (httpx.ConnectError("Connection refused"), "connect"),
        (RuntimeError("something else"), "other"),
    ],
)
def test_the_kind_of_a_failed_poll(exc: BaseException, kind: str) -> None:
    assert error_kind(exc) == kind


@pytest.mark.integration
async def test_the_health_of_the_sources(api: str) -> None:
    from sqlalchemy import update

    from radar.db import session_scope
    from radar.db.models import Article, Source, SourcePoll
    from radar.ingest import health

    now = datetime.now(UTC)
    async with session_scope() as session:
        steady = Source(
            slug="steady", name="Пишет каждый час", feed_url="https://a.example/rss", category="it"
        )
        quiet = Source(
            slug="quiet", name="Замолчал", feed_url="https://b.example/rss", category="it"
        )
        broken = Source(
            slug="broken", name="Не читается", feed_url="https://c.example/rss", category="it"
        )
        session.add_all([steady, quiet, broken])
        await session.flush()
        # Every hour for a day; the quiet one every six hours, until three days ago.
        for hours in range(0, 24):
            session.add(_article(steady.id, "a", now - timedelta(hours=hours, minutes=5)))
        for step in range(0, 10):
            session.add(_article(quiet.id, "b", now - timedelta(days=3, hours=6 * step)))
        session.add_all(
            [
                SourcePoll(
                    source_id=steady.id,
                    status="ok",
                    new_articles=2,
                    polled_at=now - timedelta(hours=1),
                ),
                SourcePoll(
                    source_id=quiet.id, status="not_modified", polled_at=now - timedelta(hours=1)
                ),
                SourcePoll(source_id=broken.id, status="ok", polled_at=now - timedelta(days=2)),
                SourcePoll(
                    source_id=broken.id,
                    status="error",
                    error_kind="stub",
                    polled_at=now - timedelta(hours=3),
                ),
                SourcePoll(
                    source_id=broken.id,
                    status="error",
                    error_kind="stub",
                    polled_at=now - timedelta(hours=2),
                ),
                SourcePoll(
                    source_id=broken.id,
                    status="error",
                    error_kind="refused",
                    polled_at=now - timedelta(hours=1),
                ),
                # Out of the day, and out of the week.
                SourcePoll(
                    source_id=steady.id,
                    status="error",
                    error_kind="dns",
                    polled_at=now - timedelta(days=2),
                ),
                SourcePoll(
                    source_id=steady.id,
                    status="error",
                    error_kind="dns",
                    polled_at=now - timedelta(days=8),
                ),
            ]
        )
        await session.execute(
            update(Source)
            .where(Source.id == broken.id)
            .values(consecutive_failures=3, last_error="Blocked: refused every method")
        )

    async with session_scope() as session:
        found = await health.health(session, now)
        purged = await health.purge(session, now)

    mine = {"Пишет каждый час", "Замолчал", "Не читается"}
    assert found.polls >= 5
    assert found.errors["stub"] == 2
    assert found.errors["refused"] == 1
    assert "dns" not in found.errors
    [failing] = [item for item in found.failing if item.name in mine]
    assert (failing.name, failing.kind, failing.failures) == ("Не читается", "refused", 3)
    assert failing.since is not None
    assert failing.since < now - timedelta(days=1)
    silent = [item for item in found.silent if item.name in mine]
    assert [item.name for item in silent] == ["Замолчал"]
    assert silent[0].longest_gap_hours == pytest.approx(6, abs=0.1)
    assert purged == 1

    async with client(api) as reader:
        await reader.post("/auth/demo")
        answer = (await reader.get("/sources/health")).json()
    assert answer["hours"] == 24
    assert answer["kinds"]["stub"] == "антибот-проверка"
    assert any(item["name"] == "Не читается" for item in answer["failing"])
    assert any(item["name"] == "Замолчал" for item in answer["silent"])

    async with session_scope() as session:
        from sqlalchemy import delete

        await session.execute(delete(Article).where(Article.url.like("https://%.example/%")))
        await session.execute(delete(Source).where(Source.slug.in_(["steady", "quiet", "broken"])))


def _article(source_id: int, host: str, published: datetime) -> object:
    from radar.db.models import Article

    stamp = published.isoformat()
    return Article(
        source_id=source_id,
        url=f"https://{host}.example/{stamp}",
        title=f"Статья {stamp}",
        summary="",
        language="ru",
        published_at=published,
        content_hash=f"{host}{stamp}",
    )
