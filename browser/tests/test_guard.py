"""The browser reaches public addresses only: routing, redirects, the proxy."""

import asyncio
import ipaddress
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import pytest

from radar_browser.guard import Guard, Refused, allowing, system_resolve
from radar_browser.proxy import FilteringProxy

# Resolves to the loopback in the test, and only it is let through there:
# it stands for a public site, 127.0.0.1 and localhost for the inside.
PUBLIC = "public.test"


def test_guard() -> Guard:
    """A guard that takes public.test for a public site on this machine."""

    async def resolve(host: str, port: int) -> list[str]:
        return ["127.0.0.1"] if host == PUBLIC else await system_resolve(host, port)

    def allow(address: ipaddress.IPv4Address | ipaddress.IPv6Address, host: str) -> bool:
        return host == PUBLIC or address.is_global

    return Guard(resolve=resolve, allow=allow)


test_guard.__test__ = False  # type: ignore[attr-defined]


async def test_named_hosts_may_be_private_and_nothing_else() -> None:
    """BROWSER_PRIVATE_HOSTS opens the names it lists, with their subdomains."""

    async def resolve(host: str, _port: int) -> list[str]:
        return ["10.0.0.5"]

    guard = Guard(resolve=resolve, allow=allowing(["farm", " "]))
    assert await guard.address("farm", 80) == "10.0.0.5"
    assert await guard.address("s001.farm", 80) == "10.0.0.5"
    for host in ("pharm", "farm.evil", "notfarm"):
        with pytest.raises(Refused):
            await guard.address(host, 80)
    with pytest.raises(Refused):
        await Guard(resolve=resolve, allow=allowing([])).address("farm", 80)


class Site(BaseHTTPRequestHandler):
    hits: ClassVar[list[str]] = []
    port = 0

    def do_GET(self) -> None:
        Site.hits.append(self.path)
        if self.path == "/hop":
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{Site.port}/secret-redirect")
            self.end_headers()
            return
        inside = f"127.0.0.1:{Site.port}"
        page = f"""<!doctype html><html><head><title>Страница</title>
<script src="http://localhost:{Site.port}/secret-script"></script></head>
<body><h1>Новости</h1><p>{"Текст новости о защите информации. " * 20}</p>
<iframe src="http://{inside}/secret-frame"></iframe>
<script>fetch("http://{inside}/secret-fetch").catch(() => {{}});
var socket = new WebSocket("ws://{inside}/secret-socket");</script>
</body></html>"""
        body = page.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_: object) -> None:
        pass


@pytest.fixture(scope="module")
def site() -> Iterator[int]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Site)
    Site.port = server.server_port
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield Site.port
    server.shutdown()


async def test_mixed_answers_are_refused() -> None:
    async def resolve(_host: str, _port: int) -> list[str]:
        return ["93.184.216.34", "10.0.0.5"]

    guard = Guard(resolve=resolve)
    with pytest.raises(Refused):
        await guard.address("rebinding.example", 443)
    assert guard.refused == ["rebinding.example:443"]


async def test_literal_addresses() -> None:
    guard = Guard()
    assert await guard.address("93.184.216.34", 80) == "93.184.216.34"
    for inside in ("127.0.0.1", "[::1]", "169.254.169.254", "192.168.1.1", "0.0.0.0"):  # noqa: S104
        with pytest.raises(Refused):
            await guard.address(inside, 80)


async def _through(proxy_url: str, request: bytes) -> bytes:
    host, port = proxy_url.removeprefix("http://").split(":")
    reader, writer = await asyncio.open_connection(host, int(port))
    writer.write(request)
    await writer.drain()
    answer = await reader.read(65536)
    writer.close()
    return answer


async def test_proxy_refuses_the_inside(site: int) -> None:
    Site.hits.clear()
    async with FilteringProxy(test_guard()) as proxy:
        tunnel = await _through(
            proxy.url, f"CONNECT 127.0.0.1:{site} HTTP/1.1\r\nHost: x\r\n\r\n".encode()
        )
        plain = await _through(
            proxy.url,
            f"GET http://localhost:{site}/secret HTTP/1.1\r\nHost: localhost\r\n\r\n".encode(),
        )
        public = await _through(
            proxy.url,
            f"GET http://{PUBLIC}:{site}/ HTTP/1.1\r\nHost: {PUBLIC}\r\n\r\n".encode(),
        )
    assert tunnel.startswith(b"HTTP/1.1 403")
    assert plain.startswith(b"HTTP/1.1 403")
    assert public.startswith(b"HTTP/1.0 200") or public.startswith(b"HTTP/1.1 200")
    assert Site.hits == ["/"]


def _browser_installed() -> bool:
    try:
        from camoufox.pkgman import installed_verstr

        installed_verstr()
    except Exception:
        return False
    return True


needs_browser = pytest.mark.skipif(not _browser_installed(), reason="camoufox is not fetched")


@pytest.fixture(scope="module")
async def renderer():  # type: ignore[no-untyped-def]
    from radar_browser.render import Renderer

    browser = Renderer(tabs=1, guard=test_guard)
    yield browser
    await browser.close()


@needs_browser
async def test_page_cannot_reach_the_inside(site: int, renderer) -> None:  # type: ignore[no-untyped-def]
    Site.hits.clear()
    page = await renderer.render(f"http://{PUBLIC}:{site}/", seconds=20)
    assert "Новости" in page.html
    assert not page.challenge
    # The script, the frame, fetch() and the socket all went for the inside.
    assert [hit for hit in Site.hits if "secret" in hit] == []
    assert f"localhost:{site}" in page.refused
    assert f"127.0.0.1:{site}" in page.refused


@needs_browser
async def test_redirect_to_the_inside_is_stopped(site: int, renderer) -> None:  # type: ignore[no-untyped-def]
    # Routing never sees a redirect the browser follows: the proxy does.
    Site.hits.clear()
    with pytest.raises(Refused):
        await renderer.render(f"http://{PUBLIC}:{site}/hop", seconds=20)
    assert Site.hits == ["/hop"]


@needs_browser
async def test_internal_address_is_not_opened(site: int, renderer) -> None:  # type: ignore[no-untyped-def]
    Site.hits.clear()
    with pytest.raises(Refused):
        await renderer.render(f"http://127.0.0.1:{site}/", seconds=20)
    assert Site.hits == []


async def test_a_name_that_does_not_resolve_goes_to_the_upstream_proxy_by_name() -> None:
    async def nowhere(host: str, port: int) -> list[str]:
        raise Refused(f"cannot resolve {host}")

    closed = Guard(resolve=nowhere)
    with pytest.raises(Refused):
        await closed.address("news.example", 443)

    through_proxy = Guard(resolve=nowhere, by_name=True)
    assert await through_proxy.address("news.example", 443) == ""
    # An address literal is still checked: the proxy is not asked to go inside.
    with pytest.raises(Refused):
        await through_proxy.address("127.0.0.1", 80)
