"""A page as a browser draws it: after its scripts and any JS challenge.

The browser is Camoufox, a Firefox built to look like a person's: it hides
the marks of automation (navigator.webdriver, the headless traits) in the
engine, not in injected scripts, and gives the window, fonts and WebGL of
an ordinary desktop. Measured against Patchright's Chromium on the sites of
the dataset (docs/DECISIONS.md, «Сбор: лестница способов чтения»), it
passed Cloudflare where Chromium got the challenge page.

Each page opens in a context of its own, Moscow time and Russian first,
with images, fonts and media not loaded. Requests are routed through a
check: one to an internal address fails at once. Everything the browser
connects to, redirects included, goes through the filtering proxy of
proxy.py, which the routing cannot be bypassed around.
"""

import asyncio
import contextlib
import html
import os
import ssl
import time
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import certifi
import httpx
from camoufox.async_api import AsyncNewBrowser
from playwright.async_api import Browser, Playwright, Request, Route, async_playwright

from radar_browser.guard import Guard, Refused
from radar_browser.proxy import REFUSED_HEADER, FilteringProxy

# A closed network resolves no outside names: through an upstream proxy a
# name that does not resolve here goes out as it is (BROWSER_DNS_VIA_PROXY).
DNS_VIA_PROXY = os.environ.get("BROWSER_DNS_VIA_PROXY", "").lower() in {"1", "true", "yes"}
# Not needed to read a page, and the most of its weight.
SKIPPED_TYPES = frozenset({"image", "media", "font"})
# What a page shows while a challenge has not let the browser in yet.
CHALLENGE_MARKERS = (
    "<title>just a moment",
    "<title>один момент",
    "window._cf_chl_opt",
    "checking your browser",
    "verifying you are human",
    "/.well-known/ddos-guard/",
)
# How long a page drawn by script may take to show its text after the
# challenge: it may sign in, ask for its data, or set a cookie and reload.
DRAW_SECONDS = 15.0
# A page with less visible text than this is not drawn yet.
DRAWN_CHARS = 200
MAX_PAGE_BYTES = 5_000_000
MAX_REDIRECTS = 5
_DROPPED = frozenset({"content-encoding", "content-length", "transfer-encoding", "connection"})


class RenderFailed(Exception):
    """The page could not be opened at all."""


@dataclass(slots=True)
class Rendered:
    url: str
    status: int
    html: str
    cookies: list[dict[str, Any]]
    user_agent: str
    # Requests turned away as internal, "host:port".
    refused: list[str] = field(default_factory=list)
    # Whether a challenge was still on the page when time ran out, and
    # whether one was passed: then the cookies are what lets a client in.
    challenge: bool = False
    solved: bool = False
    seconds: float = 0.0


class Renderer:
    """One browser for the service, a few tabs at a time."""

    def __init__(
        self,
        *,
        tabs: int = 2,
        national_ca: Path | None = None,
        guard: type[Guard] | None = None,
        prefs: dict[str, Any] | None = None,
    ) -> None:
        self._slots = asyncio.Semaphore(tabs)
        self._national_ca = national_ca if national_ca and national_ca.exists() else None
        # A test gives its own guard; the service checks for public addresses.
        self._guard = guard or Guard
        self._prefs = prefs or {}
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._starting = asyncio.Lock()

    async def start(self) -> None:
        async with self._starting:
            if self._browser is not None and self._browser.is_connected():
                return
            if self._browser is not None:
                # The browser died (out of memory, for one): its driver goes
                # with it, and both are started anew.
                await self._stop()
            if self._playwright is None:
                self._playwright = await async_playwright().start()
            browser = await AsyncNewBrowser(
                self._playwright,
                headless=True,
                locale="ru-RU",
                os="windows",
                block_webrtc=True,
                i_know_what_im_doing=True,
                firefox_user_prefs={
                    # Even the loopback goes through the proxy, which refuses it.
                    "network.proxy.allow_hijacking_localhost": True,
                    "network.proxy.no_proxies_on": "",
                    # No connections made ahead of the page asking for them.
                    "network.dns.disablePrefetch": True,
                    "network.prefetch-next": False,
                    "network.http.speculative-parallel-limit": 0,
                    **self._prefs,
                },
            )
            if not isinstance(browser, Browser):
                raise RenderFailed("Camoufox gave no browser")
            self._browser = browser

    async def close(self) -> None:
        async with self._starting:
            await self._stop()

    async def _stop(self) -> None:
        if self._browser is not None:
            with contextlib.suppress(Exception):
                await self._browser.close()
        if self._playwright is not None:
            with contextlib.suppress(Exception):
                await self._playwright.stop()
        self._browser = self._playwright = None

    async def render(
        self,
        url: str,
        *,
        proxy: str | None = None,
        seconds: float = 30.0,
        national_ca_hosts: tuple[str, ...] = (),
    ) -> Rendered:
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise Refused("only http and https URLs with a host")
        guard = self._guard()
        # Names go out to the upstream proxy unresolved only through a proxy.
        guard.by_name = DNS_VIA_PROXY and bool(proxy)
        # Checked before a tab is taken: an internal address costs nothing.
        await guard.address(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80))
        async with self._slots:
            await self.start()
            if self._browser is None:
                raise RenderFailed("the browser is not running")
            started = time.monotonic()
            async with asyncio.timeout(seconds + 5), FilteringProxy(guard, proxy) as way_out:
                try:
                    context = await self._context(way_out.url)
                except Exception:
                    # The browser went away between the check and the tab.
                    await self.start()
                    context = await self._context(way_out.url)
                national = _NationalCa(self._national_ca, national_ca_hosts, guard, proxy)
                try:
                    await context.route("**/*", lambda route: _route(route, guard, national))
                    return await _open(context, url, guard, seconds, started)
                finally:
                    with contextlib.suppress(Exception):
                        await context.close()
                    await national.aclose()

    async def _context(self, proxy: str) -> Any:
        if self._browser is None or not self._browser.is_connected():
            raise RenderFailed("the browser is not running")
        return await self._browser.new_context(
            proxy={"server": proxy},
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            service_workers="block",
        )


async def _open(context: Any, url: str, guard: Guard, seconds: float, started: float) -> Rendered:
    page = await context.new_page()
    statuses: list[int] = []
    led_inside: list[str] = []

    def on_response(response: Any) -> None:
        if response.request.is_navigation_request() and response.frame == page.main_frame:
            statuses.append(response.status)
            if response.headers.get(REFUSED_HEADER.lower()):
                # A redirect, or the page sending itself, to an internal address.
                led_inside.append(response.url)

    page.on("response", on_response)
    deadline = started + seconds
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=seconds * 1000)
    except Exception as exc:
        if guard.refused and not statuses:
            # The proxy refused the tunnel of a redirect: the browser shows an error.
            raise Refused(f"{url} led to an internal address") from exc
        if not statuses:
            raise RenderFailed(f"{type(exc).__name__}: {str(exc)[:200]}") from exc
    challenge = True
    seen = False
    html = ""
    while time.monotonic() < deadline:
        with contextlib.suppress(Exception):
            # Fails while the challenge navigates to the page it let in.
            html = await page.content()
            challenge = _challenged(html)
            seen = seen or challenge
            if not challenge:
                break
        await asyncio.sleep(0.5)
    if not challenge:
        html = await _drawn(page, html, min(deadline, time.monotonic() + DRAW_SECONDS))
        route = urlsplit(url).fragment
        if route.startswith(("/", "!")) and urlsplit(page.url).fragment != route:
            # An application that signed in came back to its front page: now
            # that it knows the browser, it is asked for the route again.
            with contextlib.suppress(Exception):
                await page.goto(url, wait_until="domcontentloaded", timeout=10_000)
                html = await _drawn(page, html, min(deadline, time.monotonic() + DRAW_SECONDS))
    if led_inside:
        raise Refused(f"{url} led to an internal address")
    final = page.url
    final_parts = urlsplit(final)
    if final_parts.hostname:
        # Where the browser ended is checked once more, as the backend does.
        await guard.address(
            final_parts.hostname, final_parts.port or (443 if final_parts.scheme == "https" else 80)
        )
    cookies = await context.cookies([final]) if final.startswith("http") else []
    agent = str(await page.evaluate("navigator.userAgent"))
    if len(html.encode()) > MAX_PAGE_BYTES:
        raise RenderFailed(f"the page is larger than {MAX_PAGE_BYTES} bytes")
    return Rendered(
        url=final,
        status=statuses[-1] if statuses else 200,
        html=html,
        cookies=list(cookies),
        user_agent=agent,
        refused=list(dict.fromkeys(guard.refused)),
        challenge=challenge,
        solved=not challenge and (seen or _let_in(statuses, cookies)),
        seconds=round(time.monotonic() - started, 2),
    )


async def _drawn(page: Any, html: str, until: float) -> str:
    """The page once its scripts have drawn it, or as it is at `until`.

    Quiet on the network is not enough: an application may sign in through
    a redirect, or a guard may set a cookie and reload, after a pause; and
    its menu may be drawn well before its list. So the page is taken when
    it has some text and the text has stopped growing.
    """
    last = -1
    while True:
        with contextlib.suppress(Exception):
            await page.wait_for_load_state("networkidle", timeout=2000)
        with contextlib.suppress(Exception):
            # Fails while the page navigates.
            html = await page.content()
            text = int(await page.evaluate("document.body ? document.body.innerText.length : 0"))
            if text >= DRAWN_CHARS and text == last:
                return html
            last = text
        if time.monotonic() >= until:
            return html
        await asyncio.sleep(0.75)


# Cookies a guard sets for a client that passed its check.
_PASS_COOKIES = frozenset({"cf_clearance", "__ddg1_", "__ddg2_", "__ddg5_", "__js_p_", "_abck"})


def _let_in(statuses: list[int], cookies: list[Any]) -> bool:
    """Whether a check passed out of sight: before the first look at the
    page, the browser was refused and then let in, or got a pass cookie."""
    refused_first = any(status in {401, 403, 429, 503} for status in statuses[:-1])
    return refused_first or any(cookie.get("name") in _PASS_COOKIES for cookie in cookies)


def _challenged(html: str) -> bool:
    head = html[:200_000].lower()
    return any(marker in head for marker in CHALLENGE_MARKERS)


async def _route(route: Route, guard: Guard, national: _NationalCa) -> None:
    request = route.request
    if request.resource_type in SKIPPED_TYPES:
        await route.abort("blockedbyclient")
        return
    parts = urlsplit(request.url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        await route.continue_()
        return
    try:
        await guard.address(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80))
    except Refused:
        await route.abort("blockedbyclient")
        return
    if national.covers(parts.hostname):
        await national.fulfil(route, request)
        return
    await route.continue_()


class _NationalCa:
    """Hosts signed by the Russian national CA, read here rather than by the browser.

    The browser trusts the usual roots only, and the national CA must not be
    trusted for every site (docs/DECISIONS.md, «Официальные источники»). So
    requests to the listed hosts and their subdomains are made from here,
    with that CA for them alone, and the browser is handed the answers.
    """

    def __init__(
        self, bundle: Path | None, hosts: tuple[str, ...], guard: Guard, proxy: str | None
    ) -> None:
        self._bundle = bundle
        self._hosts = tuple(host.lower().strip(".") for host in hosts if "." in host)
        self._guard = guard
        self._proxy = proxy
        # A client per host: an app asks for dozens of scripts at once, and a
        # new TLS connection for each was refused now and then. Per host, as
        # a connection pinned to an address must not serve another name.
        self._clients: dict[str, httpx.AsyncClient] = {}

    async def aclose(self) -> None:
        clients, self._clients = self._clients, {}
        for client in clients.values():
            await client.aclose()

    def _client(self, host: str) -> httpx.AsyncClient:
        if host not in self._clients:
            self._clients[host] = httpx.AsyncClient(
                verify=_national_context(str(self._bundle)),
                proxy=self._proxy,
                trust_env=False,
                timeout=20.0,
                limits=httpx.Limits(max_connections=6, max_keepalive_connections=6),
            )
        return self._clients[host]

    def covers(self, host: str) -> bool:
        name = host.lower().rstrip(".")
        return self._bundle is not None and any(
            name == domain or name.endswith(f".{domain}") for domain in self._hosts
        )

    async def fulfil(self, route: Route, request: Request) -> None:
        if self._bundle is None:
            await route.continue_()
            return
        headers = {
            name: value
            for name, value in (await request.all_headers()).items()
            if not name.startswith(":") and name.lower() not in {"host", "accept-encoding"}
        }
        method, body, url = request.method, request.post_data_buffer, request.url
        try:
            for _ in range(MAX_REDIRECTS + 1):
                response = await self._send(method, url, headers, body)
                following = _redirect(url, response)
                if following is None or not self.covers(urlsplit(following).hostname or ""):
                    # Not a redirect, or one elsewhere: the browser follows it
                    # itself, through the proxy.
                    break
                if request.is_navigation_request():
                    # A redirect the browser follows skips the routing, and
                    # the browser would meet the national CA on its own. A
                    # new navigation is routed: the page says where to go.
                    await route.fulfill(
                        status=200,
                        headers={
                            "Content-Type": "text/html; charset=utf-8",
                            **_cookies(response),
                        },
                        body=_REFRESH.format(url=html.escape(following, quote=True)),
                    )
                    return
                url = following
                if response.status_code == 303 or method == "POST":
                    method, body = "GET", None
        except httpx.HTTPError, Refused:
            await route.abort("failed")
            return
        await route.fulfill(
            status=response.status_code,
            headers={k: v for k, v in response.headers.items() if k.lower() not in _DROPPED},
            body=response.content[:MAX_PAGE_BYTES],
        )

    async def _send(
        self, method: str, url: str, headers: dict[str, str], body: bytes | None
    ) -> httpx.Response:
        parts = urlsplit(url)
        host = parts.hostname or ""
        address = await self._guard.address(host, parts.port or 443)
        client = self._client(host)
        for attempt in range(2):
            try:
                if self._proxy:
                    # The proxy connects by name, and TLS through it checks the name.
                    return await client.request(method, url, headers=headers, content=body)
                literal = f"[{address}]" if ":" in address else address
                netloc = f"{literal}:{parts.port}" if parts.port else literal
                target = urlunsplit((parts.scheme, netloc, parts.path, parts.query, ""))
                return await client.request(
                    method,
                    target,
                    headers={**headers, "Host": parts.netloc},
                    content=body,
                    extensions={"sni_hostname": host},
                )
            except httpx.TransportError:
                # Once more: a dropped connection of the pool is no answer.
                if attempt:
                    raise
        raise AssertionError("unreachable")


_REFRESH = '<!doctype html><meta http-equiv="refresh" content="0;url={url}">'


def _redirect(url: str, response: httpx.Response) -> str | None:
    location = str(response.headers.get("location") or "")
    if response.status_code not in {301, 302, 303, 307, 308} or not location:
        return None
    return urljoin(url, location)


def _cookies(response: httpx.Response) -> dict[str, str]:
    found = response.headers.get_list("set-cookie")
    # Playwright takes several cookies in one header, a line each.
    return {"Set-Cookie": "\n".join(found)} if found else {}


@cache
def _national_context(bundle: str) -> ssl.SSLContext:
    context = ssl.create_default_context(cafile=certifi.where())
    context.load_verify_locations(cafile=bundle)
    return context
