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


def _encoded(data: bytes | None) -> str | None:
    return base64.b64encode(data).decode() if data else None


async def render(
    url: str,
    props: dict[str, Any],
    audio: bytes | None,
    images: list[bytes | None],
    *,
    request_timeout: float,
) -> bytes:
    """The MP4 of the props, with the narration and one picture (or None) per beat."""
    payload = {
        "props": props,
        "audio": _encoded(audio),
        "images": [_encoded(image) for image in images],
    }
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
