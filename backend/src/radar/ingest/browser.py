"""The stack's own headless browser (browser/): pages drawn by script and JS challenges.

The step above curl_cffi. The service opens the page in Camoufox, a Firefox
that hides the marks of automation, waits for a challenge to let it in and
for the page's scripts to draw it, and hands back the HTML with the cookies
and the browser's User-Agent. Cookies from a passed challenge are kept for
the host like FlareSolverr's (ingest/solver.py), and the lighter steps send
them with Firefox's TLS fingerprint, so the next pages need no browser.

The address is checked here before the request and where the browser ended.
Inside the service every request of the page is checked again: the routing
turns away internal addresses, and the browser's only way out is a proxy
that connects to public addresses only, redirects included. The service
sits on the `solving` network with the ingest worker alone.
"""

from dataclasses import dataclass

import httpx

from radar.config import get_settings
from radar.ingest import solver
from radar.ingest.net import UnsafeUrlError, resolve_public
from radar.logging import get_logger

log = get_logger(__name__)


class BrowserFailed(httpx.TransportError):
    """The browser could not open the page."""


@dataclass(frozen=True, slots=True)
class Page:
    url: str
    status: int
    html: str
    # Cookies of a challenge the browser passed; None for a page that only
    # needed its scripts run, which the lighter steps cannot read anyway.
    clearance: solver.Clearance | None
    seconds: float


async def render(url: str, *, proxy: str | None = None) -> Page:
    """The page at `url` after its scripts, as the stack's browser drew it."""
    settings = get_settings()
    await resolve_public(url)
    command: dict[str, object] = {
        "url": url,
        "timeout": settings.browser_timeout_seconds,
        # The browser trusts the usual roots; these hosts it reads with the
        # national CA, for them alone (ingest/net.py).
        "national_ca_hosts": list(settings.russian_ca_hosts),
    }
    if proxy:
        command["proxy"] = proxy
    # The service is inside the stack: no address check, no proxy, no pinning.
    async with httpx.AsyncClient(
        timeout=settings.browser_timeout_seconds + 20, trust_env=False
    ) as client:
        try:
            answer = await client.post(f"{settings.browser_url.rstrip('/')}/render", json=command)
        except httpx.HTTPError as exc:
            raise BrowserFailed(f"the browser did not answer: {type(exc).__name__}") from exc
    body = (
        answer.json()
        if answer.headers.get("content-type", "").startswith("application/json")
        else {}
    )
    if answer.status_code == 422:
        # The page, or a redirect of it, led to an internal address.
        raise UnsafeUrlError(str(body.get("detail") or "the browser refused the address"))
    if answer.status_code != 200 or not isinstance(body, dict) or "html" not in body:
        detail = body.get("detail") if isinstance(body, dict) else None
        raise BrowserFailed(f"the browser failed: {str(detail or answer.status_code)[:200]}")
    final = str(body.get("url") or url)
    await resolve_public(final)
    clearance = None
    if body.get("solved"):
        clearance = solver.clearance_from(body.get("cookies"), body.get("user_agent"), "browser")
        solver.keep(clearance, url, final)
    if body.get("refused"):
        log.info("browser_refused_requests", url=url, refused=body["refused"][:10])
    return Page(
        url=final,
        status=int(body.get("status") or 200),
        html=str(body.get("html") or ""),
        clearance=clearance,
        seconds=float(body.get("seconds") or 0.0),
    )
