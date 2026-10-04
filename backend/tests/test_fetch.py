# ruff: noqa: F811  (the fixtures are imported from the other tests)
"""The fetch ladder: a site that refuses a bot is asked again the way a browser
would ask, and no step reaches an internal address."""

import asyncio
import socket
import threading
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest

from radar.ingest import browser, fetch, polite, solver
from radar.ingest.fetch import Blocked, Ladder, impersonated_get, refusal
from radar.ingest.net import UnsafeUrlError
from tests.test_telegram import offline  # noqa: F401

ARTICLE = (
    "<html><head><title>Новость</title></head><body><article><h1>Уязвимость в SCADA</h1>"
    + "".join(
        f"<p>Абзац {n}: исследователи нашли уязвимость в контроллере подстанции {n} "
        f"и описали, как атакующий получает доступ к узлу {n * 7}.</p>"
        for n in range(1, 13)
    )
    + "</article></body></html>"
)
CLOUDFLARE = (
    "<!DOCTYPE html><html><head><title>Just a moment...</title></head><body>"
    "<script>window._cf_chl_opt={cvId:'3'}</script></body></html>"
)
FEED = '<?xml version="1.0"?><rss version="2.0"><channel><title>t</title></channel></rss>'
CHROME = "Chrome/"


def answer(status: int, text: str, url: str = "https://site.example/news/1") -> httpx.Response:
    return httpx.Response(status, text=text, request=httpx.Request("GET", url))


@pytest.mark.parametrize(
    ("response", "expect", "reason"),
    [
        (answer(403, "Forbidden"), "any", "403"),
        (answer(503, CLOUDFLARE), "page", "503, заглушка Cloudflare"),
        (answer(200, CLOUDFLARE), "feed", "заглушка Cloudflare"),
        (
            answer(200, "<html><body><script src='/.well-known/ddos-guard/check'></script>"),
            "page",
            "заглушка DDoS-Guard",
        ),
        (
            answer(200, "<html><body><div id=root></div><script src=/app.js></script></body>"),
            "page",
            "пустая страница: статьи рисует скрипт",
        ),
        (
            answer(200, "<html><body><p>Коротко.</p></body></html>"),
            "article",
            "объём текста ниже порога",
        ),
        (
            answer(200, "<!doctype html><html><body>сайт</body></html>"),
            "feed",
            "HTML вместо RSS-ленты",
        ),
    ],
)
def test_refusals_are_told_from_pages(response: httpx.Response, expect: str, reason: str) -> None:
    assert refusal(response, expect) == reason  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("response", "expect"),
    [
        (answer(200, ARTICLE), "article"),
        (answer(200, FEED), "feed"),
        (answer(404, "Not found"), "article"),
        (answer(304, ""), "feed"),
        # Cloudflare's bot script on an ordinary page is no challenge.
        (
            answer(
                200,
                ARTICLE.replace(
                    "</body>", "<script src='/cdn-cgi/challenge-platform/scripts/jsd/main.js'>"
                ),
            ),
            "article",
        ),
    ],
)
def test_pages_are_not_taken_for_refusals(response: httpx.Response, expect: str) -> None:
    assert refusal(response, expect) is None  # type: ignore[arg-type]


def site(handle: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handle))


async def test_a_site_that_refuses_the_bot_is_read_with_a_browsers_headers(
    offline: None,
) -> None:
    agents: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        agent = request.headers["user-agent"]
        agents.append(agent)
        if CHROME not in agent:
            return httpx.Response(403, text="Forbidden")
        assert request.headers["accept-language"].startswith("ru-RU")
        assert request.headers["referer"] == "https://site.example/"
        return httpx.Response(200, text=ARTICLE)

    async with site(handle) as client:
        ladder = Ladder(client)
        first = await ladder.get("https://site.example/news/1", expect="article")
        second = await ladder.get("https://site.example/news/2", expect="article")

    assert first.status_code == second.status_code == 200
    # The second page starts on the step that worked for the host.
    assert [CHROME in agent for agent in agents] == [False, True, True]
    assert ladder.first is not None
    assert ladder.first.step == "browser_headers"
    assert ladder.first.note == "Шаг «обычный запрос» не сработал (403), сработал «заголовки браузера»."


async def test_a_source_starts_on_the_step_remembered_for_it(offline: None) -> None:
    agents: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        agents.append(request.headers["user-agent"])
        return httpx.Response(200, text=FEED)

    async with site(handle) as client:
        ladder = Ladder(client, remembered="browser_headers")
        await ladder.get("https://site.example/feed", expect="feed")

    assert len(agents) == 1
    assert CHROME in agents[0]
    assert ladder.first is not None
    assert (ladder.first.step, ladder.first.note) == ("browser_headers", None)


async def test_a_site_that_refuses_every_step_is_an_error_naming_each(offline: None) -> None:
    async with site(lambda _: httpx.Response(403, text=CLOUDFLARE)) as client:
        ladder = Ladder(client)
        with pytest.raises(Blocked) as refused:
            await ladder.get("https://site.example/feed", expect="feed")

    assert refused.value.attempts == (
        ("plain", "403, заглушка Cloudflare"),
        ("browser_headers", "403, заглушка Cloudflare"),
    )


async def test_a_short_page_on_every_step_is_a_short_page(offline: None) -> None:
    hits: list[str] = []
    short = "<html><body><p>Патч вышел.</p></body></html>"

    def handle(request: httpx.Request) -> httpx.Response:
        hits.append(request.url.path)
        return httpx.Response(200, text=short)

    async with site(handle) as client:
        ladder = Ladder(client)
        first = await ladder.get("https://site.example/news/1", expect="article")
        await ladder.get("https://site.example/news/2", expect="article")

    assert first.text == short
    # Both steps once for the first page; the host's next page is taken as it is.
    assert hits == ["/news/1", "/news/1", "/news/2"]
    assert ladder.first is not None
    assert (ladder.first.step, ladder.first.note) == ("plain", None)


async def test_a_site_that_is_down_is_not_a_refusal(offline: None) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with site(handle) as client:
        with pytest.raises(httpx.ConnectError):
            await Ladder(client).get("https://site.example/feed", expect="feed")


class _Site(BaseHTTPRequestHandler):
    """Refuses any client without brotli in Accept-Encoding: of the three
    steps only curl_cffi, which sends what Chrome sends, gets the page."""

    seen: list[tuple[str, str, str]] = []  # noqa: RUF012

    def do_GET(self) -> None:
        self.seen.append(
            (self.path, self.headers.get("Host", ""), self.headers.get("Accept-Encoding", ""))
        )
        if self.path == "/away":
            self.send_response(302)
            self.send_header("Location", "http://intranet.test/admin")
            self.end_headers()
            return
        ok = "br" in self.headers.get("Accept-Encoding", "")
        body = (ARTICLE if ok else "Forbidden").encode()
        self.send_response(200 if ok else 403)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_: object) -> None:
        pass


@pytest.fixture
def local_site() -> Iterator[int]:
    _Site.seen = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Site)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


@pytest.fixture
def names(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """site.test resolves to the local server; intranet.test is internal.

    No pause between requests to one host here: pacing has its own tests.
    """
    from radar.config import get_settings
    from radar.ingest import net

    monkeypatch.setenv("RADAR_FETCH_HOST_INTERVAL_SECONDS", "0")
    get_settings.cache_clear()
    polite.PACER.clear()

    async def resolve(url: str) -> str | None:
        host = httpx.URL(url).host
        if host == "site.test":
            return "127.0.0.1"
        raise UnsafeUrlError(f"host {host} resolves to a non-public address")

    monkeypatch.setattr(net, "resolve_public", resolve)
    monkeypatch.setattr(fetch, "resolve_public", resolve)
    monkeypatch.setattr(solver, "resolve_public", resolve)
    monkeypatch.setattr(browser, "resolve_public", resolve)
    yield
    get_settings.cache_clear()


async def test_a_site_that_checks_the_fingerprint_is_read_by_curl_pinned_to_the_address(
    local_site: int, names: None
) -> None:
    url = f"http://site.test:{local_site}/news/1"
    async with httpx.AsyncClient() as client:
        ladder = Ladder(client)
        response = await ladder.get(url, expect="article")

    assert response.status_code == 200
    assert "Уязвимость в SCADA" in response.text
    assert ladder.first is not None
    assert ladder.first.step == "impersonate"
    assert ladder.first.note == "Шаг «обычный запрос» не сработал (403), сработал «отпечаток Chrome»."
    # Every step went to the checked address under the site's own name.
    assert [host for _, host, _ in _Site.seen] == [f"site.test:{local_site}"] * 3


async def test_a_host_without_an_address_is_told_from_an_internal_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from radar.ingest import net

    async def no_address(*args: object, **kwargs: object) -> list[object]:
        raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", no_address)

    with pytest.raises(net.UnresolvableHostError):
        await net.resolve_public("https://nonexistent.invalid/news")


async def test_curl_does_not_follow_a_redirect_to_an_internal_address(
    local_site: int, names: None
) -> None:
    with pytest.raises(UnsafeUrlError):
        await impersonated_get(f"http://site.test:{local_site}/away")

    assert [path for path, _, _ in _Site.seen] == ["/away"]


class _Proxy(BaseHTTPRequestHandler):
    """A forward proxy that answers itself: `status` for every request, and
    each request it was handed kept in `seen`."""

    status = 200
    seen: list[str] = []  # noqa: RUF012

    def do_GET(self) -> None:
        type(self).seen.append(self.path)
        body = (ARTICLE if self.status == 200 else "Forbidden").encode()
        self.send_response(self.status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_: object) -> None:
        pass


def _serve(handler: type[BaseHTTPRequestHandler]) -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


@pytest.fixture
def proxies() -> Iterator[list[tuple[type[_Proxy], str]]]:
    """Two proxies: the first refused by every site, the second let in."""
    made = []
    servers = []
    for status in (403, 200):
        handler = type(f"Proxy{status}", (_Proxy,), {"status": status, "seen": []})
        server, url = _serve(handler)
        servers.append(server)
        made.append((handler, url))
    yield made
    for server in servers:
        server.shutdown()
        server.server_close()


def _settings(monkeypatch: pytest.MonkeyPatch, **values: str) -> None:
    from radar.config import get_settings

    for name, value in values.items():
        monkeypatch.setenv(f"RADAR_{name.upper()}", value)
    get_settings.cache_clear()


async def test_with_a_proxy_set_every_step_goes_through_it(
    local_site: int,
    names: None,
    proxies: list[tuple[type[_Proxy], str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from radar.ingest.net import build_client

    (_, _), (proxy, address) = proxies
    _settings(monkeypatch, http_proxy=address)
    url = f"http://site.test:{local_site}/news/1"
    async with build_client() as client, Ladder(client) as ladder:
        for step in fetch.LIGHT:
            response = await ladder._step(step, url, {}, None, address)
            assert response.status_code == 200
        read = await ladder.get(url, expect="article")

    assert read.status_code == 200
    # The proxy gets the site's name, not the address checked for it.
    assert proxy.seen == [url] * 4
    assert _Site.seen == []
    assert ladder.first is not None
    assert (ladder.first.step, ladder.first.proxy) == ("plain", address)


async def test_a_source_with_its_own_proxy_uses_it_instead_of_the_common_one(
    local_site: int,
    names: None,
    proxies: list[tuple[type[_Proxy], str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (common, common_address), (own, own_address) = proxies
    _settings(monkeypatch, http_proxy=common_address)
    url = f"http://site.test:{local_site}/news/1"
    async with httpx.AsyncClient() as client, Ladder(client, proxy=own_address) as ladder:
        await ladder.get(url, expect="article")

    assert (common.seen, own.seen) == ([], [url])


async def test_a_site_that_refuses_every_step_is_tried_through_the_pool_in_turn(
    names: None,
    proxies: list[tuple[type[_Proxy], str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (refused, refused_address), (let_in, let_in_address) = proxies
    _settings(monkeypatch, http_proxies=f"{refused_address},{let_in_address}")
    monkeypatch.setattr(fetch, "_rotation", iter([0]))
    _Site.seen = []
    # The site refuses both httpx steps: neither sends what it wants.
    server, _ = _serve(_Site)
    url = f"http://site.test:{server.server_address[1]}/news/1"
    try:
        async with httpx.AsyncClient() as client:
            ladder = Ladder(client, steps=["plain", "browser_headers"])
            async with ladder:
                read = await ladder.get(url, expect="article")
    finally:
        server.shutdown()
        server.server_close()

    assert read.status_code == 200
    assert [path for path, _, _ in _Site.seen] == ["/news/1", "/news/1"]
    # The first proxy was refused on its first step and left at once.
    assert (refused.seen, let_in.seen) == ([url], [url])
    assert ladder.first is not None
    assert ladder.first.proxy == let_in_address
    assert ladder.first.note == (
        f"Шаг «обычный запрос» не сработал (403), сработал «обычный запрос ({let_in_address})»."
    )
    assert ladder.first.refusals[-1] == ("plain+proxy", "403")


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1:{port}/news/1", "http://localhost:{port}/news/1", "http://10.0.0.1/"],
)
async def test_no_step_reaches_an_internal_address(
    local_site: int, url: str, proxies: list[tuple[type[_Proxy], str]]
) -> None:
    from radar.ingest.net import build_client

    target = url.format(port=local_site)
    (_, _), (proxy, address) = proxies
    async with httpx.AsyncClient() as client, build_client(proxy=address) as proxied:
        for way in (client, proxied):
            with pytest.raises(UnsafeUrlError):
                await Ladder(way).get(target)
        # Each step checks the address itself, not only the ladder before it,
        # and through a proxy before the request is handed to it.
        for step in fetch.LADDER:
            for through in (None, address):
                with pytest.raises(UnsafeUrlError):
                    await Ladder(client)._step(step, target, {}, None, through)

    assert _Site.seen == []
    assert proxy.seen == []
