"""Which addresses the browser may reach: public ones only.

The pages come from sources anyone may add, and a page can ask the browser
for anything: a script, a frame, a redirect to 127.0.0.1 or to a service of
the stack. Every connection the browser makes goes through ingest's own
proxy (proxy.py), which asks the guard, connects to the address that passed
and nowhere else; the request routing in render.py asks it too, so that a
request to an internal address fails at once and is named in the answer.
"""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable, Collection
from dataclasses import dataclass, field

Resolve = Callable[[str, int], Awaitable[list[str]]]
# Whether `address`, which `host` resolved to, may be connected to.
Allow = Callable[[ipaddress.IPv4Address | ipaddress.IPv6Address, str], bool]


class Refused(Exception):
    """The host is internal, or does not resolve."""


async def system_resolve(host: str, port: int) -> list[str]:
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise Refused(f"cannot resolve {host}") from exc
    return [str(info[4][0]) for info in infos]


def only_global(address: ipaddress.IPv4Address | ipaddress.IPv6Address, _host: str) -> bool:
    return address.is_global


def allowing(hosts: Collection[str]) -> Allow:
    """Public addresses, and any address for `hosts` and their subdomains.

    For a test stand on the stack's own network (backend/scripts/load_farm.py),
    set by whoever runs the stack (BROWSER_PRIVATE_HOSTS), never by a page.
    """
    names = frozenset(host.strip().strip(".").lower() for host in hosts if host.strip())

    def allow(address: ipaddress.IPv4Address | ipaddress.IPv6Address, host: str) -> bool:
        return address.is_global or any(host == name or host.endswith(f".{name}") for name in names)

    return allow


@dataclass(slots=True)
class Guard:
    """The check, with seams for a test: how names resolve, what is allowed."""

    resolve: Resolve = system_resolve
    allow: Allow = only_global
    # What the guard turned away, for the answer.
    refused: list[str] = field(default_factory=list)
    # A closed network with a proxy that resolves outside names: a name that
    # does not resolve here goes to the upstream proxy as it is ("" for its
    # address), and that proxy refuses internal addresses itself.
    by_name: bool = False
    # Names already checked in this render: the proxy and the routing ask alike.
    _known: dict[tuple[str, int], str] = field(default_factory=dict)

    async def address(self, host: str, port: int) -> str:
        """The address to connect to for `host`, or Refused.

        Every address the name resolves to must pass: a name that answers
        both public and private could be steered to the private one.
        """
        name = host.strip("[]").rstrip(".").lower()
        if not name:
            raise Refused("no host")
        if (name, port) in self._known:
            return self._known[name, port]
        try:
            found = [ipaddress.ip_address(name)]
        except ValueError:
            try:
                resolved = await self.resolve(name, port)
            except Refused:
                if not self.by_name:
                    raise
                self._known[name, port] = ""
                return ""
            found = [ipaddress.ip_address(item.split("%", 1)[0]) for item in resolved]
        if not found or not all(self.allow(address, name) for address in found):
            self.refused.append(f"{name}:{port}")
            raise Refused(f"{name} is not a public address")
        # IPv4 first: container networks often have no IPv6 route.
        chosen = str(next((item for item in found if item.version == 4), found[0]))
        self._known[name, port] = chosen
        return chosen
