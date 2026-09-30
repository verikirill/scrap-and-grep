"""Outbound HTTP with a guard against server-side request forgery.

Feed URLs come from users, and the service fetches them from inside the
network, so every hop is checked: only http(s), and only hosts that resolve
to public addresses. The connection then goes to the address that passed the
check, not to the host name, so a DNS server cannot answer "public" for the
check and "127.0.0.1" for the connect. Redirects are followed by hand for
the same reason.
"""

import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
import stamina

from radar.config import get_settings

MAX_REDIRECTS = 5
# Upper bound for one download. The per-read timeout alone would let a server
# that trickles a byte at a time hold a worker slot for hours.
TOTAL_TIMEOUT_SECONDS = 60.0
_REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})
_DROPPED_HEADERS = frozenset({b"content-encoding", b"content-length", b"transfer-encoding"})


class UnsafeUrlError(ValueError):
    """The URL points somewhere the service must not connect to."""


class ResponseTooLargeError(Exception):
    pass


async def resolve_public(url: str) -> str | None:
    """Validate the URL and return the address to connect to.

    Returns None when private hosts are explicitly allowed, in which case the
    caller connects by name as usual.
    """
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise UnsafeUrlError("only http and https URLs with a host are allowed")
    if get_settings().allow_private_feed_hosts:
        return None
    loop = asyncio.get_running_loop()
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        infos = await loop.getaddrinfo(parts.hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"cannot resolve host {parts.hostname}") from exc
    addresses = [ipaddress.ip_address(info[4][0]) for info in infos]
    if not addresses or any(not address.is_global for address in addresses):
        raise UnsafeUrlError(f"host {parts.hostname} resolves to a non-public address")
    # IPv4 first: container networks often have no IPv6 route.
    chosen = next((address for address in addresses if address.version == 4), addresses[0])
    return str(chosen)


async def ensure_public_url(url: str) -> None:
    await resolve_public(url)


def build_client() -> httpx.AsyncClient:
    settings = get_settings()
    return httpx.AsyncClient(
        timeout=httpx.Timeout(settings.http_timeout_seconds, connect=10.0),
        headers={"User-Agent": settings.http_user_agent, "Accept-Encoding": "gzip, deflate"},
        # No keep-alive: connections are made to pinned addresses, and a pooled
        # one must not be reused for another host name behind the same address.
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=0),
        follow_redirects=False,
    )


async def safe_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    max_bytes: int | None = None,
) -> httpx.Response:
    """GET with per-hop URL validation, a size cap and retries on transient errors."""
    limit = max_bytes or get_settings().max_feed_bytes
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        address = await resolve_public(current)
        response = await _get_once(client, current, address, headers or {}, limit)
        if response.status_code not in _REDIRECT_CODES:
            return response
        location = response.headers.get("location")
        if not location:
            return response
        current = urljoin(current, location)
    raise httpx.TooManyRedirects(f"more than {MAX_REDIRECTS} redirects")


def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500 or exc.response.status_code == 429
    return isinstance(exc, (httpx.TransportError, TimeoutError))


def _pinned(url: str, address: str | None) -> tuple[str, dict[str, str], dict[str, str]]:
    """Rewrite the URL to the validated address, keeping the name for Host and TLS."""
    if address is None:
        return url, {}, {}
    parts = urlsplit(url)
    host = parts.hostname or ""
    literal = f"[{address}]" if ":" in address else address
    netloc = f"{literal}:{parts.port}" if parts.port else literal
    target = urlunsplit((parts.scheme, netloc, parts.path, parts.query, ""))
    host_header = f"{host}:{parts.port}" if parts.port else host
    # The certificate is still verified against the host name, not the address.
    return target, {"Host": host_header}, {"sni_hostname": host}


@stamina.retry(on=_is_transient, attempts=3, timeout=90.0)
async def _get_once(
    client: httpx.AsyncClient,
    url: str,
    address: str | None,
    headers: dict[str, str],
    limit: int,
) -> httpx.Response:
    target, host_header, extensions = _pinned(url, address)
    async with (
        asyncio.timeout(TOTAL_TIMEOUT_SECONDS),
        client.stream(
            "GET", target, headers={**headers, **host_header}, extensions=extensions
        ) as response,
    ):
        if response.status_code >= 500 or response.status_code == 429:
            response.raise_for_status()
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > limit:
                raise ResponseTooLargeError(f"{url} is larger than {limit} bytes")
        # The body is already decoded; keeping the encoding header would make
        # httpx try to decompress it a second time.
        # Headers are copied as raw bytes: a redirect to a Cyrillic path arrives
        # as non-ASCII bytes in Location, and re-encoding it as text fails.
        plain_headers = [
            (name, value)
            for name, value in response.headers.raw
            if name.lower() not in _DROPPED_HEADERS
        ]
        return httpx.Response(
            status_code=response.status_code,
            headers=plain_headers,
            content=bytes(body),
            request=httpx.Request("GET", url),
        )
