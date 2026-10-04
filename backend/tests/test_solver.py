# ruff: noqa: F811  (the fixtures are imported from the other tests)
"""FlareSolverr as the ladder's last step: a challenge passed once lets the
lighter steps in with its cookies, and nothing internal is handed on."""

import json
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest

from radar.ingest import fetch, solver
from radar.ingest.fetch import Blocked, Ladder
from radar.ingest.net import UnsafeUrlError
from tests.test_fetch import ARTICLE, CLOUDFLARE, FEED, names  # noqa: F401

CHROME = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/152.0.0.0 Safari/537.36"


class _Gated(BaseHTTPRequestHandler):
    """A site behind a challenge: only the cookie of a passed one gets in."""

    seen: list[tuple[str, str]] = []  # noqa: RUF012

    def do_GET(self) -> None:
        cookie = self.headers.get("Cookie", "")
        self.seen.append((self.path, cookie))
        passed = "cf_clearance=passed" in cookie
        body = (FEED if self.path == "/feed" else ARTICLE) if passed else CLOUDFLARE
        self.send_response(200 if passed else 403)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body.encode())))
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *_: object) -> None:
        pass


class _Solver(BaseHTTPRequestHandler):
    """FlareSolverr's API: answers `solution`, keeps each command in `commands`."""

    solution: dict[str, object] = {}  # noqa: RUF012
    commands: list[dict[str, object]] = []  # noqa: RUF012

    def do_POST(self) -> None:
        command = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.commands.append(command)
        body = json.dumps(
            {"status": "ok", "message": "", "solution": {"url": command["url"], **self.solution}}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_: object) -> None:
        pass


def _serve(handler: type[BaseHTTPRequestHandler]) -> Iterator[int]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


@pytest.fixture
def gated() -> Iterator[int]:
    _Gated.seen = []
    yield from _serve(_Gated)


@pytest.fixture
def flaresolverr(monkeypatch: pytest.MonkeyPatch) -> Iterator[type[_Solver]]:
    from radar.config import get_settings

    _Solver.commands = []
    _Solver.solution = {
        "status": 200,
        # What Chrome shows for a feed: its XML viewer, not the feed.
        "response": "<html><body><div>This XML file does not appear to have any style",
        "userAgent": CHROME,
        "cookies": [
            {"name": "cf_clearance", "value": "passed", "expires": time.time() + 3600},
            {"name": "__cf_bm", "value": "bm", "expires": -1},
        ],
    }
    for port in _serve(_Solver):
        monkeypatch.setenv("RADAR_FLARESOLVERR_URL", f"http://127.0.0.1:{port}")
        get_settings.cache_clear()
        solver._clearances.clear()
        yield _Solver
        solver._clearances.clear()
    get_settings.cache_clear()


async def test_a_challenge_passed_by_flaresolverr_lets_curl_in_with_its_cookies(
    gated: int, names: None, flaresolverr: type[_Solver]
) -> None:
    feed = f"http://site.test:{gated}/feed"
    async with httpx.AsyncClient() as client, Ladder(client) as ladder:
        response = await ladder.get(feed, expect="feed")
        article = await ladder.get(f"http://site.test:{gated}/news/1", expect="article")

    # The feed itself, not Chrome's view of it.
    assert response.text == FEED
    assert ladder.first is not None
    assert ladder.first.step == "solver"
    assert ladder.first.note == (
        "Шаг «обычный запрос» не сработал (403, заглушка Cloudflare), сработал «FlareSolverr»."
    )
    assert [command["url"] for command in flaresolverr.commands] == [feed]
    assert "Уязвимость в SCADA" in article.text
    # Three refused steps, the feed again with the cookies, and the article
    # on the first try with them: the browser was asked once.
    assert [cookie != "" for _, cookie in _Gated.seen] == [False, False, False, True, True]


async def test_a_source_read_by_flaresolverr_starts_with_its_cookies_next_time(
    gated: int, names: None, flaresolverr: type[_Solver]
) -> None:
    feed = f"http://site.test:{gated}/feed"
    async with httpx.AsyncClient() as client:
        async with Ladder(client) as first:
            await first.get(feed, expect="feed")
        _Gated.seen = []
        async with Ladder(client, remembered="solver") as second:
            await second.get(feed, expect="feed")

    assert _Gated.seen == [("/feed", "cf_clearance=passed; __cf_bm=bm")]
    assert len(flaresolverr.commands) == 1
    assert second.first is not None
    assert second.first.step == "solver"


async def test_flaresolverr_is_not_asked_for_a_page_that_is_only_short(
    names: None, flaresolverr: type[_Solver]
) -> None:
    short = "<html><body><p>Патч вышел.</p></body></html>"
    page = httpx.MockTransport(lambda _: httpx.Response(200, text=short))
    async with (
        httpx.AsyncClient(transport=page) as client,
        Ladder(client, steps=["plain", "browser_headers", "solver"]) as ladder,
    ):
        response = await ladder.get("http://site.test/news/1", expect="article")

    assert response.text == short
    assert flaresolverr.commands == []


async def test_a_refusal_flaresolverr_calls_200_is_still_a_refusal(
    names: None, flaresolverr: type[_Solver]
) -> None:
    nginx = "<html><head><title>403 Forbidden</title></head><body>nginx</body></html>"
    flaresolverr.solution = {"status": 200, "response": nginx, "userAgent": CHROME, "cookies": []}
    refused = httpx.MockTransport(lambda _: httpx.Response(403, text=nginx))
    async with (
        httpx.AsyncClient(transport=refused) as client,
        Ladder(client, steps=["plain", "solver"]) as ladder,
    ):
        with pytest.raises(Blocked) as blocked:
            await ladder.get("http://site.test/feed", expect="feed")

    assert blocked.value.attempts == (
        ("plain", "403, страница 403"),
        ("solver", "страница 403"),
    )


async def test_flaresolverr_does_not_hand_on_a_page_it_was_redirected_to_inside(
    names: None, flaresolverr: type[_Solver]
) -> None:
    flaresolverr.solution = {
        "url": "http://intranet.test/admin",
        "status": 200,
        "response": ARTICLE,
        "userAgent": CHROME,
        "cookies": [],
    }
    with pytest.raises(UnsafeUrlError):
        await solver.solve("http://site.test/news/1")
    # Nor is it asked for an internal address at all.
    with pytest.raises(UnsafeUrlError):
        await solver.solve("http://intranet.test/admin")

    assert [command["url"] for command in flaresolverr.commands] == ["http://site.test/news/1"]


async def test_flaresolverr_gets_the_proxy_with_its_login_apart(
    names: None, flaresolverr: type[_Solver]
) -> None:
    await solver.solve("http://site.test/news/1", proxy="socks5://reader:secret@proxy.example:1080")

    assert flaresolverr.commands[0]["proxy"] == {
        "url": "socks5://proxy.example:1080",
        "username": "reader",
        "password": "secret",
    }
    assert fetch.label("solver+proxy") == "FlareSolverr через прокси"
