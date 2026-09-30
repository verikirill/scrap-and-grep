"""HTTP API of the voice service. Only the media worker calls it.

POST /v1/speech  {"sentences": [...], "language": "Russian", "voice": null, "gap_ms": 380}
    -> {"voice", "sample_rate", "segments": [{"start_ms", "end_ms"}], "audio": base64 WAV}
GET  /health     -> {"status": "ok", "model", "device", "loaded"}
"""

import asyncio
import base64
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Literal

import uvicorn
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, StringConstraints

from radar_tts.engine import Config, Engine, UnknownSpeaker

log = logging.getLogger("radar_tts")

# A short is a hook, up to six items and an outro: eight lines. The rest is
# headroom, not an invitation to read books aloud.
MAX_SENTENCES = 12
MAX_CHARS = 400
# Requests waiting for the model at once; more would only time out.
MAX_WAITING = 4
# The 0.6B model fits next to the digest LLM on a 12 GB card (docs/DECISIONS.md).
DEFAULT_MODEL = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
DEFAULT_SPEAKER = "Aiden"
DEFAULT_INSTRUCT = "Energetic news anchor, clear diction, fast pace."

Sentence = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_CHARS)
]
Language = Literal["Auto", "Russian", "English"]


class SpeechIn(BaseModel):
    sentences: list[Sentence] = Field(min_length=1, max_length=MAX_SENTENCES)
    language: Language = "Russian"
    voice: Annotated[str, StringConstraints(max_length=40, pattern=r"^[A-Za-z_]+$")] | None = None
    gap_ms: int = Field(default=380, ge=0, le=2000)


class SegmentOut(BaseModel):
    start_ms: int
    end_ms: int


class SpeechOut(BaseModel):
    voice: str
    sample_rate: int
    segments: list[SegmentOut]
    audio: str


def _env(name: str, default: str) -> str:
    # Compose passes unset variables as empty strings.
    return os.environ.get(name) or default


def _config() -> Config:
    return Config(
        model=_env("TTS_MODEL", DEFAULT_MODEL),
        speaker=_env("TTS_SPEAKER", DEFAULT_SPEAKER),
        instruct=_env("TTS_INSTRUCT", DEFAULT_INSTRUCT),
        device=_env("TTS_DEVICE", "auto"),
        keep_alive_seconds=float(_env("TTS_KEEP_ALIVE_SECONDS", "600")),
    )


engine = Engine(_config())
_waiting = 0


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    reaper = asyncio.create_task(engine.unload_when_idle())
    try:
        yield
    finally:
        reaper.cancel()


app = FastAPI(title="Radar TTS", lifespan=lifespan, docs_url=None, redoc_url=None)


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "model": engine.config.model,
        "device": engine.device,
        "loaded": engine.loaded,
    }


@app.post("/v1/speech")
async def speech(payload: SpeechIn) -> SpeechOut:
    global _waiting
    if _waiting >= MAX_WAITING:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="busy")
    _waiting += 1
    try:
        result = await engine.speak(
            payload.sentences,
            language=payload.language,
            speaker=payload.voice,
            gap_ms=payload.gap_ms,
        )
    except UnknownSpeaker as exc:
        # Languages are checked by the request schema; anything else that
        # goes wrong is a 500, not a caller's mistake.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)[:300]) from exc
    finally:
        _waiting -= 1
    return SpeechOut(
        voice=result.voice,
        sample_rate=result.sample_rate,
        segments=[SegmentOut(start_ms=start, end_ms=end) for start, end in result.segments],
        audio=base64.b64encode(result.wav).decode(),
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    uvicorn.run(
        app,
        host=os.environ.get("TTS_HOST", "127.0.0.1"),
        port=int(os.environ.get("TTS_PORT", "8200")),
    )
