# ruff: noqa: F811  (the fixtures are imported from the other tests)
"""Politeness of the crawler: pauses per host, Retry-After, robots.txt noted
but not obeyed, and a source that keeps failing polled less often."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from radar.ingest import polite
from radar.ingest.fetch import Blocked, Ladder
from radar.ingest.polite import HostResting, retry_after, robots_allows
from radar.ingest.service import BACKOFF_MAX, backoff
from tests.test_accounts_api import api, database  # noqa: F401
from tests.test_fetch import ARTICLE, FEED
from tests.test_telegram import offline  # noqa: F401


@pytest.fixture
def paced(monkeypatch: pytest.MonkeyPatch, offline: None) -> list[float]:
    """A second between requests to one host; the pauses taken are listed."""
    from radar.config import get_settings

    monkeypatch.setenv("RADAR_FETCH_HOST_INTERVAL_SECONDS", "1")
    get_settings.cache_clear()
    pauses: list[float] = []

    async def sleep(seconds: float) -> None:
        pauses.append(seconds)

    monkeypatch.setattr(polite.asyncio, "sleep", sleep)
    return pauses


def site(handle: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handle))


async def test_requests_to_one_host_keep_a_pause_with_a_random_part(paced: list[float]) -> None:
    async with (
        site(lambda _: httpx.Response(200, text=ARTICLE)) as client,
        Ladder(client) as ladder,
    ):
        await ladder.get("https://one.example/news/1")
        await ladder.get("https://one.example/news/2")
        await ladder.get("https://two.example/news/1")

    # The second page of one.example waited; two.example did not.
    assert len(paced) == 1
    assert 0.9 <= paced[0] <= 1.5


async def test_a_site_that_says_too_many_requests_is_not_dodged_but_waited_for(
    paced: list[float],
) -> None:
    hits: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        hits.append(request.headers["user-agent"])
        return httpx.Response(429, headers={"Retry-After": "120"}, text="slow down")

    async with site(handle) as client, Ladder(client) as ladder:
        with pytest.raises(Blocked) as told:
            await ladder.get("https://busy.example/feed", expect="feed")
        # Asked to wait two minutes: the run does not sit and wait for it.
        with pytest.raises(HostResting):
            await ladder.get("https://busy.example/feed", expect="feed")

    # No climb to another fingerprint after the 429.
    assert len(hits) == 1
    assert told.value.attempts == (("plain", "429"),)


async def test_a_short_retry_after_is_waited_out(paced: list[float]) -> None:
    answers = iter(
        [
            httpx.Response(503, headers={"Retry-After": "5"}, text="maintenance"),
            httpx.Response(200, text=FEED),
        ]
    )
    async with site(lambda _: next(answers)) as client, Ladder(client) as ladder:
        response = await ladder.get("https://busy.example/feed", expect="feed")

    assert response.status_code == 200
    assert len(paced) == 1
    assert 4.0 <= paced[0] <= 5.0


def test_retry_after_is_read_in_seconds_and_as_a_date() -> None:
    later = (datetime.now(UTC) + timedelta(seconds=90)).strftime("%a, %d %b %Y %H:%M:%S GMT")

    assert retry_after(httpx.Response(429, headers={"Retry-After": "30"})) == 30.0
    assert 80 <= (retry_after(httpx.Response(429, headers={"Retry-After": later})) or 0) <= 90
    assert retry_after(httpx.Response(429, headers={"Retry-After": "soon"})) is None
    assert retry_after(httpx.Response(429)) is None


@pytest.mark.parametrize(
    ("answer", "verdict"),
    [
        (httpx.Response(200, text="User-agent: *\nDisallow: /feed\n"), False),
        (httpx.Response(200, text="User-agent: ScrapGrepBot\nAllow: /\n"), True),
        (httpx.Response(404), True),
        (httpx.Response(500), None),
    ],
)
async def test_robots_txt_is_read_once_and_answered(
    offline: None, answer: httpx.Response, verdict: bool | None
) -> None:
    asked: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        asked.append(request.url.path)
        return answer

    async with site(handle) as client:
        first = await robots_allows(client, "https://rules.example/feed")
        again = await robots_allows(client, "https://rules.example/feed")

    assert first == again == verdict
    assert asked == ["/robots.txt"]


def test_a_failing_source_rests_longer_and_longer_up_to_a_day() -> None:
    assert backoff(1) == timedelta(0)
    assert timedelta(minutes=13) <= backoff(2) <= timedelta(minutes=17)
    assert timedelta(minutes=27) <= backoff(3) <= timedelta(minutes=33)
    assert backoff(20) <= BACKOFF_MAX * 1.1


@pytest.mark.integration
async def test_a_source_that_keeps_failing_is_left_out_of_polls_until_it_rests(
    api: str, offline: None
) -> None:
    from radar.cache import get_cache
    from radar.db import session_scope
    from radar.db.models import Source
    from radar.ingest.service import enabled_source_ids, ingest_source

    async with session_scope() as session:
        source = Source(
            slug="flaky",
            name="Шаткий сайт",
            feed_url="https://flaky.example/feed",
            category="security",
        )
        session.add(source)
        await session.flush()
        source_id = source.id
    up = False
    feed = (
        '<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>'
        "<item><title>Новость</title><link>https://flaky.example/news/1</link>"
        "<pubDate>Wed, 30 Sep 2026 10:00:00 GMT</pubDate></item></channel></rss>"
    )

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /\n")
        if not up:
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200, text=feed)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        await ingest_source(source_id, client, get_cache())
        after_one = source_id in await enabled_source_ids()
        await ingest_source(source_id, client, get_cache())
        after_two = source_id in await enabled_source_ids()
        later = source_id in await enabled_source_ids(datetime.now(UTC) + timedelta(hours=1))
        up = True
        # An administrator's refresh reads it at once, rest or not.
        recovered = await ingest_source(source_id, client, get_cache())

    async with session_scope() as session:
        source = await session.get(Source, source_id)
    assert (after_one, after_two, later) == (True, False, True)
    assert recovered.new_articles == 1
    assert source is not None
    assert source.retry_at is None
    assert source.consecutive_failures == 0
    # robots.txt forbade everything; it was noted, and the feed read anyway.
    assert source.robots_allowed is False


async def test_an_unchanged_page_is_not_downloaded_again_on_any_step(offline: None) -> None:
    sent: list[str | None] = []

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(request.headers.get("if-none-match"))
        if "Chrome/" not in request.headers["user-agent"]:
            return httpx.Response(403, text="Forbidden")
        if request.headers.get("if-none-match") == '"v1"':
            return httpx.Response(304)
        return httpx.Response(200, text=ARTICLE, headers={"ETag": '"v1"'})

    async with site(handle) as client, Ladder(client) as ladder:
        response = await ladder.get(
            "https://waf.example/news", headers={"If-None-Match": '"v1"'}, expect="page"
        )

    # The browser's headers do not drop the validator: the site answers 304.
    assert response.status_code == 304
    assert sent == ['"v1"', '"v1"']
