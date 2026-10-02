"""Politeness: how often one host is asked, and what it said about it.

Requests to one host leave a pause between them, with a random part, so
that the full texts of a feed are not fetched in one burst. A host that
answers 429 or 503 with Retry-After is not asked again before then; one
that asks for long is skipped for the run instead of being waited on.

robots.txt is read and its verdict recorded, but it does not stop the
reading: the sources are public news pages the task asks to read
(docs/DECISIONS.md, «Сбор»).
"""

import asyncio
import random
import time
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from radar.config import get_settings
from radar.ingest.net import safe_get
from radar.logging import get_logger

log = get_logger(__name__)

# Longest a request waits for its host's turn; past that the host rests.
MAX_WAIT_SECONDS = 60.0
# Longest Retry-After taken at its word.
MAX_RETRY_AFTER_SECONDS = 3600.0
ROBOTS_TTL_SECONDS = 24 * 3600.0
ROBOTS_MAX_BYTES = 500_000
# A site that holds a bot's connection open would hold the run up for it.
ROBOTS_TIMEOUT_SECONDS = 5.0
# The name robots.txt rules are matched against.
ROBOTS_AGENT = "TailGrepBot"


class HostResting(httpx.HTTPError):
    """The host asked not to be asked again yet (Retry-After)."""

    def __init__(self, host: str, seconds: float) -> None:
        super().__init__(f"{host} asked to wait {seconds:.0f} s more")
        self.host = host
        self.seconds = seconds


class HostPacer:
    """When each host may be asked next, in this process.

    One event loop runs the requests, so a slot is taken without a lock:
    nothing awaits between reading the next free moment and moving it on.
    """

    def __init__(self) -> None:
        self._next: dict[str, float] = {}

    async def wait(self, key: str) -> None:
        interval = get_settings().fetch_host_interval_seconds
        now = time.monotonic()
        slot = max(now, self._next.get(key, 0.0))
        if slot - now > MAX_WAIT_SECONDS:
            raise HostResting(key, slot - now)
        self._next[key] = slot + interval * (1 + random.random() / 2)  # noqa: S311
        if slot > now:
            await asyncio.sleep(slot - now)

    def hold(self, key: str, seconds: float) -> None:
        """Not before `seconds` from now: what Retry-After asked for."""
        until = time.monotonic() + min(seconds, MAX_RETRY_AFTER_SECONDS)
        self._next[key] = max(self._next.get(key, 0.0), until)

    def clear(self) -> None:
        self._next.clear()


PACER = HostPacer()


def retry_after(response: httpx.Response) -> float | None:
    """Seconds the site asked to wait, from Retry-After in seconds or as a date."""
    value = response.headers.get("retry-after", "").strip()
    if not value:
        return None
    if value.isdigit():
        return float(value)
    try:
        moment = parsedate_to_datetime(value)
    except TypeError, ValueError:
        return None
    return max(moment.timestamp() - time.time(), 0.0)


# robots.txt by host: the parsed rules, or None when there were none to read.
_robots: dict[str, tuple[float, RobotFileParser | None]] = {}


async def robots_allows(client: httpx.AsyncClient, url: str) -> bool | None:
    """Whether the site's robots.txt lets the bot read `url`; None when unknown.

    Read once a day per host. The answer is recorded, never obeyed.
    """
    parts = urlsplit(url)
    host = parts.hostname or ""
    cached = _robots.get(host)
    if cached is None or cached[0] < time.monotonic():
        rules: RobotFileParser | None = None
        try:
            async with asyncio.timeout(ROBOTS_TIMEOUT_SECONDS):
                response = await safe_get(
                    client,
                    f"{parts.scheme}://{parts.netloc}/robots.txt",
                    max_bytes=ROBOTS_MAX_BYTES,
                    retry=False,
                )
            if response.status_code == 200:
                rules = RobotFileParser()
                rules.parse(response.text.splitlines())
            elif 400 <= response.status_code < 500:
                # No robots.txt is leave to read everything.
                rules = RobotFileParser()
                rules.parse([])
        except Exception as exc:  # whatever the site does, it is only a note
            log.info("robots_unreadable", host=host, error=type(exc).__name__)
        _robots[host] = (time.monotonic() + ROBOTS_TTL_SECONDS, rules)
        cached = _robots[host]
    rules = cached[1]
    if rules is None:
        return None
    allowed = rules.can_fetch(ROBOTS_AGENT, url)
    if not allowed:
        log.info("robots_disallowed", url=url)
    return allowed
