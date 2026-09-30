"""Client of the Remotion render service (shorts/server/server.ts)."""

import base64
from typing import Any

import httpx

from radar.logging import get_logger

log = get_logger(__name__)

_MP4_BRAND_AT = slice(4, 8)


class RendererBusy(Exception):
    """The renderer has a full queue; the task should try again later."""


class RendererRejected(Exception):
    """The renderer refused the props: a bug on our side, not worth a retry."""


async def render(
    url: str, props: dict[str, Any], audio: bytes | None, *, request_timeout: float
) -> bytes:
    payload = {"props": props, "audio": base64.b64encode(audio).decode() if audio else None}
    async with httpx.AsyncClient(timeout=httpx.Timeout(request_timeout, connect=10.0)) as client:
        response = await client.post(f"{url.rstrip('/')}/v1/render", json=payload)
    if response.status_code == httpx.codes.SERVICE_UNAVAILABLE:
        raise RendererBusy
    if response.status_code == httpx.codes.BAD_REQUEST:
        # The detail names fields and limits, never the text itself.
        log.error("short_props_rejected", detail=response.text[:2000])
        raise RendererRejected
    response.raise_for_status()
    video = response.content
    if video[_MP4_BRAND_AT] != b"ftyp":
        raise ValueError("the renderer returned something other than MP4")
    return video
