"""Reading a page the way the site lets it be read: a ladder of methods.

Many sites refuse a client that calls itself a bot, or any client that does
not look like a browser: 401 and 403 from a WAF, a Cloudflare or DDoS-Guard
challenge, an empty page that a script fills in. The ladder asks the plain
way first and climbs only when the answer is such a refusal:

1. httpx with the honest bot User-Agent;
2. httpx with the headers of a current Chrome;
3. curl_cffi with the TLS (JA3/JA4) and HTTP/2 fingerprint of Chrome;
4. FlareSolverr, a browser in the stack that passes a JS challenge
   (ingest/solver.py); its cookies then let the lower steps in.

The step that worked is remembered per host for the rest of the run, and the
caller stores it per source, so the next run starts there. Every step checks
each hop the way ingest/net.py does: only public addresses, and the
connection pinned to the address that passed the check.
"""

import asyncio
import contextlib
import itertools
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import cache
from importlib.resources import files
from pathlib import Path
from typing import Literal
from urllib.parse import urljoin, urlsplit

import certifi
import httpx
import trafilatura
from curl_cffi import CurlOpt
from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException
from selectolax.lexbor import LexborHTMLParser

from radar.config import get_settings
from radar.ingest import bdu, solver
from radar.ingest.net import (
    MAX_REDIRECTS,
    RUSSIAN_CA_BUNDLE,
    TOTAL_TIMEOUT_SECONDS,
    ResponseTooLargeError,
    UnsafeUrlError,
    build_client,
    proxy_name,
    proxy_of,
    resolve_public,
    safe_get,
    trusts_russian_ca,
)
from radar.ingest.polite import PACER, retry_after
from radar.logging import get_logger

log = get_logger(__name__)

Step = Literal["plain", "browser_headers", "impersonate", "solver"]
# What the caller is about to read: a refusal looks different for each.
Expect = Literal["any", "feed", "page", "article"]

LADDER: tuple[Step, ...] = ("plain", "browser_headers", "impersonate", "solver")
# Steps that run a browser: slow, so tried only after a refusal by the site,
# and only where the browser is reachable (the ingest worker, not the api).
HEAVY: frozenset[Step] = frozenset({"solver"})
LIGHT: tuple[Step, ...] = tuple(step for step in LADDER if step not in HEAVY)
LABELS: dict[str, str] = {
    "plain": "обычный запрос",
    "browser_headers": "заголовки браузера",
    "impersonate": "curl_cffi",
    "solver": "FlareSolverr",
}
# What sites answer a client they will not serve.
REFUSALS = frozenset({401, 403, 429, 503})
# A challenge page is small; a page with a marker below and much text is an
# ordinary page that happens to load the vendor's script.
CHALLENGE_MAX_BYTES = 100_000
CHALLENGES: tuple[tuple[str, str], ...] = (
    ("<title>just a moment...</title>", "заглушка Cloudflare"),
    ("window._cf_chl_opt", "заглушка Cloudflare"),
    ("cf-browser-verification", "заглушка Cloudflare"),
    ("attention required! | cloudflare", "заглушка Cloudflare"),
    ("check.ddos-guard.net", "заглушка DDoS-Guard"),
    ("/.well-known/ddos-guard/", "заглушка DDoS-Guard"),
    ("<title>ddos-guard</title>", "заглушка DDoS-Guard"),
    ("checking your browser", "проверка браузера"),
    ("verifying you are human", "проверка браузера"),
    ("please enable javascript and cookies to continue", "проверка браузера"),
    # FlareSolverr says 200 whatever the site answered: its refusal is in the page.
    ("<title>403 forbidden</title>", "страница 403"),
    ("<title>401 authorization required</title>", "страница 401"),
    ("<title>access denied</title>", "страница «доступ запрещён»"),
)
NO_ANSWER = "нет ответа"
THIN_FEED = "страница вместо ленты"
JS_SHELL = "пустая страница-приложение"
SHORT_TEXT = "текст короче порога"
# Refusals judged by the page's content, not by the site's answer.
CONTENT_REASONS = frozenset({THIN_FEED, JS_SHELL, SHORT_TEXT})
# A page whose visible text is shorter than this, but which has scripts, is
# an application drawn in the browser.
JS_SHELL_CHARS = 200
_DROPPED_HEADERS = frozenset({"content-encoding", "content-length", "transfer-encoding"})


class Blocked(httpx.HTTPError):
    """Every step of the ladder was refused."""

    def __init__(self, url: str, attempts: Sequence[tuple[str, str]]) -> None:
        tried = "; ".join(f"{label(step)}: {reason}" for step, reason in attempts)
        super().__init__(f"{url} refused every method ({tried})")
        self.attempts = tuple(attempts)


def label(step: str) -> str:
    """For a person: "impersonate+proxy" is "curl_cffi через прокси"."""
    base, _, proxied = step.partition("+")
    return LABELS.get(base, base) + (" через прокси" if proxied else "")


@dataclass(slots=True)
class Outcome:
    """How a URL was read: the step, and why the steps below it did not do."""

    step: str
    refusals: list[tuple[str, str]] = field(default_factory=list)
    # The proxy the page came through, if any.
    proxy: str | None = None

    @property
    def note(self) -> str | None:
        """For a person: "403 на шаге «обычный запрос», прочитан через curl_cffi"."""
        if not self.refusals:
            return None
        first_step, first_reason = self.refusals[0]
        way = label(self.step) + (f" ({proxy_name(self.proxy)})" if self.proxy else "")
        return f"{first_reason} на шаге «{label(first_step)}», прочитан через {way}"


@dataclass(slots=True)
class _Climb:
    """What one URL's way up the ladder has met so far."""

    outcome: Outcome
    last_error: Exception | None = None
    # The site answered 429 with Retry-After: no other step until then.
    told_to_wait: bool = False
    # The first answer refused only for its content: the step, the answer, why.
    thin: tuple[Step, httpx.Response, str] | None = None


class Ladder:
    """One run's way of reading pages, sharing what it learns between them.

    `remembered` is the step that worked last time for the source; the run
    starts there and climbs from it, and only then tries the steps below.

    `proxy` is the source's own proxy; without it RADAR_HTTP_PROXY, when
    set, carries every request. Otherwise a site that refused every step
    is climbed again through the proxies of RADAR_HTTP_PROXIES, the next
    one taken whenever a proxy is refused too.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        remembered: str | None = None,
        steps: Sequence[Step] | None = None,
        proxy: str | None = None,
    ) -> None:
        self._client = client
        settings = get_settings()
        available = steps if steps is not None else LADDER
        self._steps = tuple(
            step
            for step in available
            if step in LADDER
            and (step != "impersonate" or settings.fetch_impersonate)
            and (step != "solver" or settings.flaresolverr_url)
        )
        self._remembered = remembered if remembered in self._steps else None
        # The proxy every request goes through, when there is one.
        self._proxy = proxy or proxy_of(client) or settings.http_proxy or None
        self._pool = [] if self._proxy else list(settings.http_proxies)
        # Clients for proxies other than the given client's, closed at the end.
        self._clients: dict[str, httpx.AsyncClient] = {}
        # The step and the proxy that worked for each host during this run.
        self._hosts: dict[str, tuple[Step, str | None]] = {}
        # Hosts whose pages look thin on every step: taken as they are.
        self._thin_hosts: set[str] = set()
        # How the first URL read was read: the source's own address.
        self.first: Outcome | None = None

    async def __aenter__(self) -> Ladder:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        clients, self._clients = self._clients, {}
        for client in clients.values():
            await client.aclose()

    def _order(self, start: str | None) -> list[Step]:
        for index, step in enumerate(self._steps):
            if step == start:
                return [*self._steps[index:], *self._steps[:index]]
        return list(self._steps)

    def _passes(self, host: str) -> list[str | None]:
        """The proxies to climb through: the usual way first, then the pool,
        from the proxy that worked for the host or from the next in turn."""
        if not self._pool:
            return [self._proxy]
        known = self._hosts.get(host)
        if known is not None and known[1] in self._pool:
            first = self._pool.index(known[1])
        else:
            first = next(_rotation) % len(self._pool)
        return [None, *self._pool[first:], *self._pool[:first]]

    async def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        max_bytes: int | None = None,
        expect: Expect = "any",
    ) -> httpx.Response:
        """The page at `url`, read by the lowest step the site accepts.

        A refusal on every step raises Blocked. An answer that is no refusal
        (200, 304, 404, 500) is returned as it is, for the caller to judge.
        A page that only looked empty on every step is returned too: it is
        a short page, not a closed one.
        """
        await resolve_public(url)
        host = urlsplit(url).hostname or ""
        known = self._hosts.get(host)
        climb = _Climb(Outcome(step=""))
        for proxy in self._passes(host):
            pooled = proxy is not None and proxy != self._proxy
            if pooled and (climb.thin is not None or not _refused(climb)):
                # Thin pages or a site that is down: no proxy changes that.
                break
            start = known[0] if known is not None and known[1] == proxy else self._remembered
            if start in HEAVY and solver.clearance_for(url) is not None:
                # The cookies of a passed challenge let a lighter step in.
                start = "impersonate"
            climb.told_to_wait = False
            for step in self._order(start):
                if step in HEAVY and not _worth_a_browser(climb) and start != step:
                    continue
                read = await self._try(climb, step, proxy, url, headers or {}, max_bytes, expect)
                if read is not None:
                    return self._read(host, url, step, proxy, climb.outcome, read)
                if climb.told_to_wait:
                    # Another fingerprint would only dodge the limit.
                    break
                if pooled and _proxy_refused(climb):
                    # The site refuses this proxy too: on to the next one.
                    break
        outcome = climb.outcome
        content_only = all(reason in CONTENT_REASONS for _, reason in outcome.refusals)
        if climb.thin is not None and (content_only or climb.thin[2] == SHORT_TEXT):
            # No step read more: the site's pages are like that, and its
            # next pages are not asked for again on every step. An empty
            # script shell or HTML for a feed after a refusal is no page,
            # but what the site shows a client it has not let in.
            step, response, _ = climb.thin
            if content_only:
                self._thin_hosts.add(host)
                outcome.refusals.clear()
            else:
                outcome.refusals = [item for item in outcome.refusals if item[0] != step]
            return self._read(host, url, step, self._proxy, outcome, response)
        if self.first is None:
            self.first = outcome
        if climb.last_error is not None and all(
            reason.startswith("ошибка") for _, reason in outcome.refusals
        ):
            # Not a refusal but a site that is down or unreachable.
            raise climb.last_error
        raise Blocked(url, outcome.refusals)

    async def _try(
        self,
        climb: _Climb,
        step: Step,
        proxy: str | None,
        url: str,
        headers: dict[str, str],
        max_bytes: int | None,
        expect: Expect,
    ) -> httpx.Response | None:
        """The response of one step, or None after noting why it is no good."""
        pooled = proxy is not None and proxy != self._proxy
        name = f"{step}+proxy" if pooled else step
        refusals = climb.outcome.refusals
        host = urlsplit(url).hostname or ""
        # Paced by host and by the way out: a proxy is another client to the site.
        pace = f"{host} {proxy or ''}"
        await PACER.wait(pace)
        try:
            response = await self._step(step, url, headers, max_bytes, proxy, expect)
        except UnsafeUrlError, ResponseTooLargeError:
            raise
        except (httpx.TimeoutException, TimeoutError) as exc:
            # Some WAFs never answer a bot: McAfee's holds the connection open.
            refusals.append((name, NO_ANSWER))
            climb.last_error = exc
            return None
        except (httpx.TransportError, RequestException) as exc:
            refusals.append((name, f"ошибка соединения ({type(exc).__name__})"))
            climb.last_error = exc
            return None
        if response.status_code in {429, 503} and (wait := retry_after(response)) is not None:
            PACER.hold(pace, wait)
            climb.told_to_wait = response.status_code == 429
        reason = await asyncio.to_thread(refusal, response, expect)
        if reason in CONTENT_REASONS and host in self._thin_hosts:
            reason = None
        if reason is None:
            return response
        if reason in CONTENT_REASONS and climb.thin is None and not pooled:
            climb.thin = (step, response, reason)
        refusals.append((name, reason))
        return None

    def _read(
        self,
        host: str,
        url: str,
        step: Step,
        proxy: str | None,
        outcome: Outcome,
        response: httpx.Response,
    ) -> httpx.Response:
        if step in {"browser_headers", "impersonate"} and solver.clearance_for(url):
            # Let in on the cookies FlareSolverr got: the source still needs it.
            step = "solver"
        outcome.step = step
        outcome.proxy = proxy
        # A solved challenge is followed by the cookies on the lighter step.
        self._hosts[host] = ("impersonate" if step in HEAVY else step, proxy)
        if self.first is None:
            self.first = outcome
        if outcome.refusals:
            log.info("fetch_climbed", url=url, step=step, note=outcome.note)
        return response

    @property
    def client(self) -> httpx.AsyncClient:
        """The client for the way every request goes: the proxy, if one is set."""
        return self._client_for(self._proxy)

    def _client_for(self, proxy: str | None) -> httpx.AsyncClient:
        if proxy == proxy_of(self._client):
            return self._client
        key = proxy or ""
        if key not in self._clients:
            self._clients[key] = build_client(proxy=key)
        return self._clients[key]

    async def _step(
        self,
        step: Step,
        url: str,
        headers: dict[str, str],
        max_bytes: int | None,
        proxy: str | None,
        expect: Expect = "any",
    ) -> httpx.Response:
        if step == "solver":
            return await self._solve(url, headers, max_bytes, proxy, expect)
        passed = solver.clearance_for(url) if step != "plain" else None
        if passed is not None:
            # A challenge passed before: its cookies, from the browser that got them.
            headers = {"Cookie": passed.cookie_header, **headers}
        if step == "impersonate":
            if passed is not None:
                headers = {"User-Agent": passed.user_agent, **headers}
            return await impersonated_get(url, headers=headers, max_bytes=max_bytes, proxy=proxy)
        if step == "browser_headers":
            headers = {**browser_headers(url), **headers}
            if passed is not None:
                headers["User-Agent"] = passed.user_agent
        return await safe_get(
            self._client_for(proxy), url, headers=headers, max_bytes=max_bytes, retry=False
        )

    async def _solve(
        self,
        url: str,
        headers: dict[str, str],
        max_bytes: int | None,
        proxy: str | None,
        expect: Expect,
    ) -> httpx.Response:
        """The page through FlareSolverr; the site's own answer with the
        cookies it gave, when it takes them, rather than the browser's view."""
        solution = await solver.solve(url, proxy=proxy)
        if solution.clearance is not None:
            again = {
                "Cookie": solution.clearance.cookie_header,
                "User-Agent": solution.clearance.user_agent,
                **headers,
            }
            with contextlib.suppress(httpx.TransportError, RequestException):
                response = await impersonated_get(
                    url, headers=again, max_bytes=max_bytes, proxy=proxy
                )
                if await asyncio.to_thread(refusal, response, expect) is None:
                    return response
        page = solution.html.encode()
        limit = max_bytes or get_settings().max_feed_bytes
        if len(page) > limit:
            raise ResponseTooLargeError(f"{url} is larger than {limit} bytes")
        return httpx.Response(
            status_code=solution.status,
            headers={"Content-Type": "text/html; charset=utf-8"},
            content=page,
            request=httpx.Request("GET", solution.url),
        )


# Where the next run starts in the proxy pool, so that runs share the load.
_rotation = itertools.count()


def _refused(climb: _Climb) -> bool:
    """Whether the site refused the client, rather than being down."""
    return any(
        reason == NO_ANSWER or reason[:3].isdigit() or reason.startswith("заглушка")
        for _, reason in climb.outcome.refusals
    )


def _worth_a_browser(climb: _Climb) -> bool:
    """A refusal by the site, or a page drawn by script: what a browser helps."""
    return _refused(climb) or any(reason == JS_SHELL for _, reason in climb.outcome.refusals)


def _proxy_refused(climb: _Climb) -> bool:
    reason = climb.outcome.refusals[-1][1] if climb.outcome.refusals else ""
    return reason.startswith(("403", "429")) or reason == NO_ANSWER


def browser_headers(url: str) -> dict[str, str]:
    """What Chrome sends when a person opens the page from the site's front page."""
    parts = urlsplit(url)
    version = _chrome_version(get_settings().browser_user_agent)
    return {
        "User-Agent": get_settings().browser_user_agent,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        "Referer": f"{parts.scheme}://{parts.netloc}/",
        "Sec-CH-UA": f'"Google Chrome";v="{version}", "Not?A_Brand";v="8", '
        f'"Chromium";v="{version}"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }


def _chrome_version(user_agent: str) -> str:
    _, _, rest = user_agent.partition("Chrome/")
    return rest.split(".", 1)[0] or "141"


async def impersonated_get(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    max_bytes: int | None = None,
    proxy: str | None = None,
) -> httpx.Response:
    """GET through curl_cffi with Chrome's TLS and HTTP/2 fingerprint.

    Redirects are followed by hand, each hop checked; the connection goes to
    the checked address through curl's RESOLVE, so the name stays in SNI and
    Host. Through a proxy the address is checked all the same, before the
    request is handed over. The answer comes back as an httpx response, like
    the other steps.
    """
    limit = max_bytes or get_settings().max_feed_bytes
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        address = await resolve_public(current)
        response = await _impersonated_once(current, address, headers or {}, limit, proxy)
        location = response.headers.get("location")
        if response.status_code not in {301, 302, 303, 307, 308} or not location:
            return response
        current = urljoin(current, location)
    raise httpx.TooManyRedirects(f"more than {MAX_REDIRECTS} redirects")


async def _impersonated_once(
    url: str, address: str | None, headers: dict[str, str], limit: int, proxy: str | None
) -> httpx.Response:
    parts = urlsplit(url)
    host = parts.hostname or ""
    options: dict[CurlOpt, object] = {CurlOpt.CAINFO: _ca_file(trusts_russian_ca(host))}
    if address is not None:
        port = parts.port or (443 if parts.scheme == "https" else 80)
        with contextlib.suppress(UnicodeError):
            host = host.encode("idna").decode("ascii")
        literal = f"[{address}]" if ":" in address else address
        options[CurlOpt.RESOLVE] = [f"{host}:{port}:{literal}"]
    settings = get_settings()
    async with (
        asyncio.timeout(TOTAL_TIMEOUT_SECONDS),
        AsyncSession(
            impersonate="chrome",
            timeout=settings.http_timeout_seconds,
            allow_redirects=False,
            trust_env=False,
            proxy=proxy,
            curl_options=options,
        ) as session,
    ):
        response = await session.get(
            url,
            headers={"Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8", **headers},
            stream=True,
        )
        body = bytearray()
        async for chunk in response.aiter_content():
            body.extend(chunk)
            if len(body) > limit:
                raise ResponseTooLargeError(f"{url} is larger than {limit} bytes")
        kept = [
            (name, value)
            for name, value in response.headers.multi_items()
            if name.lower() not in _DROPPED_HEADERS
        ]
        return httpx.Response(
            status_code=response.status_code,
            headers=kept,
            content=bytes(body),
            request=httpx.Request("GET", url),
        )


@cache
def _ca_file(national: bool) -> str:
    """A CA file for curl: certifi, plus the Russian national CA for its hosts."""
    if not national:
        return certifi.where()
    bundle = Path(certifi.where()).read_text("ascii")
    bundle += "\n" + files("radar.ingest").joinpath(RUSSIAN_CA_BUNDLE).read_text("ascii")
    # The backend's file system is read-only but for /tmp.
    with tempfile.NamedTemporaryFile(
        "w", suffix=".pem", prefix="radar-ca-", delete=False, encoding="ascii"
    ) as handle:
        handle.write(bundle)
    return handle.name


def refusal(response: httpx.Response, expect: Expect) -> str | None:
    """Why this answer is a refusal rather than the page, or None for the page."""
    status = response.status_code
    body = response.content
    small = len(body) <= CHALLENGE_MAX_BYTES
    marker = _challenge(body) if small else None
    if status in REFUSALS:
        return f"{status}, {marker}" if marker else str(status)
    if status >= 300:
        return None
    if marker:
        return marker
    if expect == "feed":
        head = body[:2000].lstrip().lower()
        if head.startswith((b"<!doctype html", b"<html")) and not any(
            tag in body[:20_000].lower() for tag in (b"<rss", b"<feed", b"<rdf:rdf")
        ):
            return THIN_FEED
        return None
    if expect in {"page", "article"} and _is_js_shell(response.text):
        return JS_SHELL
    if expect == "article" and not bdu.is_vulnerability_page(str(response.request.url)):
        text = trafilatura.extract(response.text, include_comments=False) or ""
        if len(text) < get_settings().fetch_min_article_chars:
            return SHORT_TEXT
    return None


def _challenge(body: bytes) -> str | None:
    lowered = body.decode("utf-8", "ignore").lower()
    return next((label for marker, label in CHALLENGES if marker in lowered), None)


def _is_js_shell(page: str) -> bool:
    if "<script" not in page.lower():
        return False
    tree = LexborHTMLParser(page)
    for node in tree.css("script, style, noscript, template"):
        node.decompose()
    body = tree.body
    text = body.text(separator=" ", strip=True) if body is not None else ""
    return len(text) < JS_SHELL_CHARS
