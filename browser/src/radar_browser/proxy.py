"""The browser's only way out: a proxy that connects to public addresses only.

Request routing does not see everything a browser does. A redirect is
followed inside the browser without asking the route again (checked: a
302 to 127.0.0.1 went straight through), and WebSockets and service workers
have their own paths. So the browser is given this proxy for every request,
and the proxy decides: it resolves the name, lets the guard check every
address, and connects to the address that passed, not to the name, so a
second DNS answer cannot point it inside.

HTTPS goes through as a CONNECT tunnel: TLS stays between the browser and
the site, with the browser's own fingerprint. Plain HTTP is forwarded one
request per connection. With an upstream proxy (the source's own or the
corporate one) the address is checked all the same before the upstream
proxy is asked to connect by name.
"""

import asyncio
import contextlib
from urllib.parse import urlsplit

from python_socks.async_.asyncio import Proxy

from radar_browser.guard import Guard, Refused

HEAD_LIMIT = 64 * 1024
REFUSED_HEADER = "X-Radar-Refused"
CONNECT_TIMEOUT_SECONDS = 15.0
_HOP_HEADERS = frozenset(
    {b"proxy-connection", b"proxy-authorization", b"connection", b"keep-alive"}
)


class FilteringProxy:
    """One render's proxy, on a port of its own on the loopback interface."""

    def __init__(self, guard: Guard, upstream: str | None = None) -> None:
        self._guard = guard
        self._upstream = upstream
        self._server: asyncio.Server | None = None
        self._tasks: set[asyncio.Task[None]] = set()

    async def __aenter__(self) -> FilteringProxy:
        self._server = await asyncio.start_server(self._serve, "127.0.0.1", 0)
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._server is not None:
            self._server.close()
        for task in list(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    @property
    def url(self) -> str:
        if self._server is None:
            raise RuntimeError("the proxy is not started")
        port = self._server.sockets[0].getsockname()[1]
        return f"http://127.0.0.1:{port}"

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        if task is not None:
            self._tasks.add(task)
        try:
            await self._handle(reader, writer)
        except OSError, asyncio.IncompleteReadError, asyncio.LimitOverrunError, ValueError:
            pass
        finally:
            if task is not None:
                self._tasks.discard(task)
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        head = await reader.readuntil(b"\r\n\r\n")
        if len(head) > HEAD_LIMIT:
            return
        line, _, rest = head.partition(b"\r\n")
        method, target, version = line.decode("latin-1").split(" ", 2)
        if method == "CONNECT":
            host, _, port_text = target.rpartition(":")
            upstream = await self._open(writer, host, int(port_text or 443))
            if upstream is None:
                return
            writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await writer.drain()
            await _pipe(reader, writer, *upstream)
            return
        parts = urlsplit(target)
        if parts.scheme != "http" or not parts.hostname:
            await _answer(writer, 400, "Bad Request")
            return
        upstream = await self._open(writer, parts.hostname, parts.port or 80)
        if upstream is None:
            return
        path = parts.path or "/"
        if parts.query:
            path += f"?{parts.query}"
        # One request per connection: a reused connection must not carry a
        # request for another host to the address this one was checked for.
        headers = [
            item
            for item in rest.split(b"\r\n")
            if item and item.split(b":", 1)[0].strip().lower() not in _HOP_HEADERS
        ]
        forwarded = b"\r\n".join(
            [f"{method} {path} {version}".encode("latin-1"), *headers, b"Connection: close"]
        )
        upstream[1].write(forwarded + b"\r\n\r\n")
        await _pipe(reader, writer, *upstream)

    async def _open(
        self, writer: asyncio.StreamWriter, host: str, port: int
    ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter] | None:
        try:
            address = await self._guard.address(host, port)
        except Refused:
            await _answer(writer, 403, "Forbidden", refused=True)
            return None
        try:
            async with asyncio.timeout(CONNECT_TIMEOUT_SECONDS):
                if self._upstream:
                    # The upstream proxy connects by name, so that TLS through
                    # it still checks the site's certificate against the name.
                    sock = await Proxy.from_url(self._upstream, rdns=True).connect(
                        host.strip("[]"), port
                    )
                    return await asyncio.open_connection(sock=sock)
                return await asyncio.open_connection(address, port)
        except Exception:  # the upstream proxy's errors are its own types
            await _answer(writer, 502, "Bad Gateway")
            return None


async def _answer(
    writer: asyncio.StreamWriter, status: int, reason: str, *, refused: bool = False
) -> None:
    # The mark tells the renderer that the page itself led inside.
    mark = f"{REFUSED_HEADER}: 1\r\n" if refused else ""
    head = f"HTTP/1.1 {status} {reason}\r\n{mark}Content-Length: 0\r\nConnection: close\r\n\r\n"
    writer.write(head.encode())
    with contextlib.suppress(OSError):
        await writer.drain()


async def _pipe(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    upstream_reader: asyncio.StreamReader,
    upstream_writer: asyncio.StreamWriter,
) -> None:
    async def copy(source: asyncio.StreamReader, sink: asyncio.StreamWriter) -> None:
        with contextlib.suppress(OSError):
            while chunk := await source.read(65536):
                sink.write(chunk)
                await sink.drain()
        with contextlib.suppress(OSError):
            sink.close()

    try:
        await asyncio.gather(
            copy(client_reader, upstream_writer), copy(upstream_reader, client_writer)
        )
    finally:
        upstream_writer.close()
