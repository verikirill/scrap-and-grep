"""HTTP API of the browser service: "give me this page after its scripts".

It runs on a network of its own with the ingest worker only (docker-compose,
`solving`): no route to the database, the queues or the api, and every
connection of the browser goes through the check of guard.py besides.
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from radar_browser.guard import Refused
from radar_browser.render import Renderer, RenderFailed

TIMEOUT_SECONDS = float(os.environ.get("BROWSER_TIMEOUT_SECONDS", "30"))
renderer = Renderer(
    tabs=int(os.environ.get("BROWSER_TABS", "2")),
    national_ca=Path(os.environ.get("BROWSER_NATIONAL_CA", "/app/certs/russian_trusted_ca.pem")),
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await renderer.start()
    yield
    await renderer.close()


app = FastAPI(title="Radar browser", lifespan=lifespan)


class RenderIn(BaseModel):
    url: str = Field(max_length=4000)
    # The source's proxy or the corporate one: http://, https:// or socks5://.
    proxy: str | None = Field(default=None, max_length=500)
    timeout: float | None = Field(default=None, gt=0)
    # Hosts signed by the Russian national CA (RADAR_RUSSIAN_CA_HOSTS).
    national_ca_hosts: list[str] = Field(default_factory=list, max_length=50)


class RenderOut(BaseModel):
    url: str
    status: int
    html: str
    cookies: list[dict[str, Any]]
    user_agent: str
    refused: list[str]
    challenge: bool
    solved: bool
    seconds: float


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/render")
async def render(payload: RenderIn) -> RenderOut:
    try:
        page = await renderer.render(
            payload.url,
            proxy=payload.proxy,
            seconds=min(payload.timeout or TIMEOUT_SECONDS, TIMEOUT_SECONDS),
            national_ca_hosts=tuple(payload.national_ca_hosts),
        )
    except Refused as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(
            status.HTTP_504_GATEWAY_TIMEOUT, detail="the page took too long"
        ) from exc
    except RenderFailed as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return RenderOut(
        url=page.url,
        status=page.status,
        html=page.html,
        cookies=page.cookies,
        user_agent=page.user_agent,
        refused=page.refused,
        challenge=page.challenge,
        solved=page.solved,
        seconds=page.seconds,
    )


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))  # noqa: S104
