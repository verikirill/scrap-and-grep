# ruff: noqa: F811  (the fixtures are imported from the other tests)
"""The stack's browser as the step above curl_cffi: pages drawn by script,
challenges, FlareSolverr only after it, and nothing internal handed on."""

import json
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler

import httpx
import pytest

from radar.ingest import fetch, solver
from radar.ingest.fetch import Ladder
from radar.ingest.net import UnsafeUrlError
from tests.test_fetch import ARTICLE, FEED, names  # noqa: F401
from tests.test_solver import _Gated, _serve, _Solver, flaresolverr, gated  # noqa: F401

FIREFOX = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0"
SHELL = "<html><body><div id=app></div><script src=/app.js></script></body></html>"


class _Shell(BaseHTTPRequestHandler):
    """A site drawn by script: every client but a browser gets the empty app."""

    seen: list[str] = []  # noqa: RUF012

    def do_GET(self) -> None:
        self.seen.append(self.path)
        body = SHELL.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_: object) -> None:
        pass


class _Browser(BaseHTTPRequestHandler):
    """The browser service's API: answers `page` (or `status` with `detail`)."""

    page: dict[str, object] = {}  # noqa: RUF012
    status = 200
    commands: list[dict[str, object]] = []  # noqa: RUF012

    def do_POST(self) -> None:
        command = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.commands.append(command)
        answer = (
            {"url": command["url"], **self.page}
            if self.status == 200
            else {"detail": "intranet.test is not a public address"}
        )
        body = json.dumps(answer).encode()
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_: object) -> None:
        pass


@pytest.fixture
def shell() -> Iterator[int]:
    _Shell.seen = []
    yield from _serve(_Shell)


@pytest.fixture
def stack_browser(monkeypatch: pytest.MonkeyPatch) -> Iterator[type[_Browser]]:
    from radar.config import get_settings

    _Browser.commands = []
    _Browser.status = 200
    _Browser.page = {
        "status": 200,
        "html": ARTICLE,
        "cookies": [],
        "user_agent": FIREFOX,
        "refused": [],
        "challenge": False,
        "solved": False,
        "seconds": 2.5,
    }
    for port in _serve(_Browser):
        monkeypatch.setenv("RADAR_BROWSER_URL", f"http://127.0.0.1:{port}")
        get_settings.cache_clear()
        solver._clearances.clear()
        yield _Browser
        solver._clearances.clear()
    get_settings.cache_clear()


async def test_a_page_drawn_by_script_is_read_by_the_browser(
    shell: int, names: None, stack_browser: type[_Browser]
) -> None:
    async with httpx.AsyncClient() as client, Ladder(client) as ladder:
        page = await ladder.get(f"http://site.test:{shell}/#/news", expect="page")
        article = await ladder.get(f"http://site.test:{shell}/#/news/1", expect="article")

    assert "Уязвимость в SCADA" in page.text
    assert "Уязвимость в SCADA" in article.text
    assert ladder.first is not None
    assert ladder.first.step == "browser"
    assert ladder.first.note == (
        "Шаг «обычный запрос» не сработал (пустая страница: статьи рисует скрипт), сработал «браузер»."
    )
    # The browser opens the route itself, fragment and all, and is told which
    # hosts the national CA may sign for.
    assert [command["url"] for command in stack_browser.commands] == [
        f"http://site.test:{shell}/#/news",
        f"http://site.test:{shell}/#/news/1",
    ]
    assert "bduasutp.fstec.ru" in stack_browser.commands[0]["national_ca_hosts"]  # type: ignore[operator]
    # Three light steps for the first page; the next went to the browser at
    # once: without a challenge's cookies a lighter step only gets the app.
    assert len(_Shell.seen) == 3


async def test_a_challenge_the_browser_passed_lets_curl_in_as_firefox(
    gated: int, names: None, stack_browser: type[_Browser], monkeypatch: pytest.MonkeyPatch
) -> None:
    stack_browser.page = {
        **stack_browser.page,
        "html": "<html><body>Firefox's view of the feed</body></html>",
        "solved": True,
        "cookies": [{"name": "cf_clearance", "value": "passed", "expires": time.time() + 600}],
    }
    likes: list[str] = []
    real = fetch._impersonated_once

    async def spy(*args: object) -> httpx.Response:
        likes.append(str(args[-1]))
        return await real(*args)  # type: ignore[arg-type]

    monkeypatch.setattr(fetch, "_impersonated_once", spy)
    feed = f"http://site.test:{gated}/feed"
    async with httpx.AsyncClient() as client, Ladder(client) as ladder:
        response = await ladder.get(feed, expect="feed")
        article = await ladder.get(f"http://site.test:{gated}/news/1", expect="article")

    assert response.text == FEED
    assert "Уязвимость в SCADA" in article.text
    assert ladder.first is not None
    assert ladder.first.step == "browser"
    assert len(stack_browser.commands) == 1
    # Chrome's fingerprint without cookies, then Firefox's with the browser's.
    assert likes == ["chrome", "firefox", "firefox"]
    assert _Gated.seen[-1] == ("/news/1", "cf_clearance=passed")
    passed = solver.clearance_for(feed)
    assert passed is not None
    assert passed.step == "browser"
    assert passed.firefox


async def test_flaresolverr_is_asked_only_after_the_browser_is_refused(
    gated: int,
    names: None,
    stack_browser: type[_Browser],
    flaresolverr: type[_Solver],
) -> None:
    nginx = "<html><head><title>403 Forbidden</title></head><body>nginx</body></html>"
    stack_browser.page = {**stack_browser.page, "status": 403, "html": nginx}
    async with httpx.AsyncClient() as client, Ladder(client) as ladder:
        response = await ladder.get(f"http://site.test:{gated}/feed", expect="feed")

    assert response.text == FEED
    assert ladder.first is not None
    assert ladder.first.step == "solver"
    assert ("browser", "403, страница 403") in ladder.first.refusals
    assert len(stack_browser.commands) == 1
    assert len(flaresolverr.commands) == 1


async def test_a_page_that_leads_inside_is_not_handed_on(
    shell: int, names: None, stack_browser: type[_Browser]
) -> None:
    # The service turned the address away (422): the ladder stops at once.
    stack_browser.status = 422
    async with httpx.AsyncClient() as client, Ladder(client) as ladder:
        with pytest.raises(UnsafeUrlError):
            await ladder.get(f"http://site.test:{shell}/", expect="page")

    # Where the browser ended is checked here too.
    stack_browser.status = 200
    stack_browser.page = {**stack_browser.page, "url": "http://intranet.test/admin"}
    async with httpx.AsyncClient() as client, Ladder(client) as ladder:
        with pytest.raises(UnsafeUrlError):
            await ladder.get(f"http://site.test:{shell}/", expect="page")


async def test_the_browser_step_is_off_without_the_service(shell: int, names: None) -> None:
    async with httpx.AsyncClient() as client, Ladder(client) as ladder:
        response = await ladder.get(f"http://site.test:{shell}/", expect="page")
    # Taken as it is: no step read more.
    assert response.text == SHELL
    assert fetch.label("browser+proxy") == "браузер через прокси"
