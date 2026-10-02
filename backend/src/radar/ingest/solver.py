"""FlareSolverr: a browser in the stack that passes a challenge for the ladder.

When curl_cffi is refused too, the page is opened in FlareSolverr's Chrome,
which runs the challenge's script and waits for it to let the browser in.
What comes back is the page as the browser drew it, and the cookies the
site set for passing, `cf_clearance` among them. The cookies, with the
browser's User-Agent, are kept for the host for a while: the lower steps
send them, so one solved challenge serves the next pages and runs, and a
feed comes as XML rather than as Chrome's view of it.

The service fetches the URL itself, so it gets the same address check as
the other steps, before the request and on the address it ended at. It
runs on a network of its own, with no route to the database, the queues
or the api.
"""

import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from radar.config import get_settings
from radar.ingest.net import resolve_public
from radar.logging import get_logger

log = get_logger(__name__)

# Cookies a challenge set are trusted no longer than this, whatever they say.
CLEARANCE_TTL_SECONDS = 1800


class SolverFailed(httpx.TransportError):
    """FlareSolverr could not open the page or pass its challenge."""


@dataclass(frozen=True, slots=True)
class Clearance:
    """What a passed challenge leaves: cookies and the browser that got them.

    `step` is the ladder's step that passed it: FlareSolverr's Chrome or the
    stack's own browser (ingest/browser.py), a Firefox.
    """

    cookies: dict[str, str]
    user_agent: str
    until: float
    step: str = "solver"

    @property
    def firefox(self) -> bool:
        return "Firefox/" in self.user_agent

    @property
    def cookie_header(self) -> str:
        return "; ".join(f"{name}={value}" for name, value in self.cookies.items())


@dataclass(frozen=True, slots=True)
class Solution:
    url: str
    status: int
    html: str
    clearance: Clearance | None


# Passed challenges by host, in this process.
_clearances: dict[str, Clearance] = {}


def clearance_for(url: str) -> Clearance | None:
    host = urlsplit(url).hostname or ""
    found = _clearances.get(host)
    if found is None:
        return None
    if found.until < time.monotonic():
        _clearances.pop(host, None)
        return None
    return found


def forget(url: str) -> None:
    """Drop the host's cookies: the site no longer takes them."""
    _clearances.pop(urlsplit(url).hostname or "", None)


async def solve(url: str, *, proxy: str | None = None) -> Solution:
    """The page at `url` as FlareSolverr's browser got it."""
    settings = get_settings()
    await resolve_public(url)
    timeout = settings.flaresolverr_timeout_seconds
    command: dict[str, object] = {
        "cmd": "request.get",
        "url": url,
        "maxTimeout": int(timeout * 1000),
    }
    if proxy:
        command["proxy"] = _proxy(proxy)
    # The service is inside the stack: no address check, no proxy, no pinning.
    async with httpx.AsyncClient(timeout=timeout + 15, trust_env=False) as client:
        try:
            answer = await client.post(f"{settings.flaresolverr_url.rstrip('/')}/v1", json=command)
        except httpx.HTTPError as exc:
            raise SolverFailed(f"FlareSolverr did not answer: {type(exc).__name__}") from exc
    body = (
        answer.json()
        if answer.headers.get("content-type", "").startswith("application/json")
        else {}
    )
    solution = body.get("solution") if isinstance(body, dict) else None
    if answer.status_code != 200 or body.get("status") != "ok" or not isinstance(solution, dict):
        message = (
            str(body.get("message") or answer.status_code)[:200] if isinstance(body, dict) else ""
        )
        raise SolverFailed(f"FlareSolverr failed: {message}")
    final = str(solution.get("url") or url)
    # The browser followed redirects on its own: where it ended is checked now,
    # and a page from an internal address is not handed on.
    await resolve_public(final)
    clearance = clearance_from(solution.get("cookies"), solution.get("userAgent"), "solver")
    keep(clearance, url, final)
    return Solution(
        url=final,
        status=int(solution.get("status") or 200),
        html=str(solution.get("response") or ""),
        clearance=clearance,
    )


def keep(clearance: Clearance | None, *urls: str) -> None:
    """Remember a passed challenge for the hosts of `urls`."""
    if clearance is None:
        return
    for url in urls:
        _clearances[urlsplit(url).hostname or ""] = clearance


def clearance_from(cookies: object, agent: object, step: str) -> Clearance | None:
    """The cookies a browser was given, as the ladder keeps them."""
    if not isinstance(cookies, list) or not isinstance(agent, str) or not cookies:
        return None
    jar: dict[str, str] = {}
    expires = time.time() + CLEARANCE_TTL_SECONDS
    for cookie in cookies:
        if not isinstance(cookie, dict) or "name" not in cookie or "value" not in cookie:
            continue
        jar[str(cookie["name"])] = str(cookie["value"])
        stamp = cookie.get("expires") or cookie.get("expiry")
        if isinstance(stamp, int | float) and stamp > 0:
            expires = min(expires, float(stamp))
    if not jar:
        return None
    left = max(expires - time.time(), 0.0)
    return Clearance(cookies=jar, user_agent=agent, until=time.monotonic() + left, step=step)


def _proxy(proxy: str) -> dict[str, str]:
    """FlareSolverr takes the proxy's login and password apart from its address."""
    parts = urlsplit(proxy)
    port = f":{parts.port}" if parts.port else ""
    found = {"url": f"{parts.scheme}://{parts.hostname}{port}"}
    if parts.username:
        found["username"] = parts.username
    if parts.password:
        found["password"] = parts.password
    return found
