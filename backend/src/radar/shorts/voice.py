"""The narration: Qwen3-TTS through the voice service, or silence with timing.

A video without a voice is still a video: captions carry the story. So a
missing or failing voice service costs the sound, not the whole video.
"""

import base64
from itertools import pairwise
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel, Field, ValidationError

from radar.logging import get_logger
from radar.shorts.model import Narration, Segment
from radar.shorts.speech import spoken
from radar.shorts.timing import estimate_segments

log = get_logger(__name__)

LANGUAGE = "Russian"
# Silence between lines: enough to hear a new item start.
GAP_MS = 380
_WAV_HEADER = 12


class _SegmentOut(BaseModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)


class _SpeechOut(BaseModel):
    voice: str = Field(max_length=60)
    sample_rate: int
    segments: list[_SegmentOut]
    audio: str


VOICE_ID_PATTERN = r"^[A-Za-z0-9_-]{1,40}$"
# What speaks: the voice service, Qwen3-TTS on a GPU of the stack, or Yandex
# SpeechKit; a narration's voice is named "<engine>:<speaker>".
VoiceEngine = Literal["qwen3-tts", "yandex"]


class VoiceOption(BaseModel):
    """A voice a reader can pick for the narration."""

    id: str = Field(pattern=VOICE_ID_PATTERN)
    title: str = Field(min_length=1, max_length=40)
    default: bool = False
    # Whether a short sample of the voice can be heard before it is picked.
    sample: bool = False


class Voice(Protocol):
    """What a video or a brief asks of a voice: our service or SpeechKit."""

    async def voices(self) -> list[VoiceOption]: ...

    async def speak(self, lines: list[str], voice: str | None = None) -> Narration: ...


def _voice_options(listing: object) -> list[VoiceOption]:
    """The well-formed entries of the service's list; one bad entry does not
    take the whole choice away."""
    if not isinstance(listing, list):
        raise ValueError("the voice service returned something other than a list")
    voices = []
    for entry in listing:
        try:
            voices.append(VoiceOption.model_validate(entry))
        except ValidationError:
            log.warning("short_voice_skipped", entry=str(entry)[:80])
    return voices


def silent(lines: list[str]) -> Narration:
    return Narration(segments=estimate_segments(lines), audio=None, voice=None)


def _is_wav(data: bytes) -> bool:
    return len(data) > _WAV_HEADER and data[:4] == b"RIFF" and data[8:12] == b"WAVE"


class VoiceClient:
    def __init__(
        self,
        url: str,
        *,
        timeout: float,
        speaker: str = "",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._url = url.rstrip("/")
        self._timeout = httpx.Timeout(timeout, connect=10.0)
        self._speaker = speaker
        self._transport = transport

    async def voices(self) -> list[VoiceOption]:
        """The voices the service offers; empty when it has no choice to give."""
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.get(f"{self._url}/v1/voices")
        response.raise_for_status()
        return _voice_options(response.json())

    async def speak(self, lines: list[str], voice: str | None = None) -> Narration:
        payload = {
            "sentences": [spoken(line) for line in lines],
            "language": LANGUAGE,
            "voice": voice or self._speaker or None,
            "gap_ms": GAP_MS,
        }
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.post(f"{self._url}/v1/speech", json=payload)
        response.raise_for_status()
        out = _SpeechOut.model_validate(response.json())
        audio = base64.b64decode(out.audio, validate=True)
        if not _is_wav(audio):
            raise ValueError("the voice service returned something other than WAV")
        if len(out.segments) != len(lines):
            raise ValueError(f"{len(out.segments)} segments for {len(lines)} lines")
        segments = tuple(Segment(item.start_ms, item.end_ms) for item in out.segments)
        if any(later.start_ms < earlier.end_ms for earlier, later in pairwise(segments)) or any(
            segment.end_ms <= segment.start_ms for segment in segments
        ):
            raise ValueError("the voice service returned overlapping or empty segments")
        return Narration(segments=segments, audio=audio, voice=f"qwen3-tts:{out.voice}")


async def narrate(client: Voice | None, lines: list[str], voice: str | None = None) -> Narration:
    """Speak the lines, or time them for a silent video if the voice fails.

    A picked voice the service refuses (it was removed after the reader
    chose it) gives way to the service's default voice."""
    if client is None:
        return silent(lines)
    try:
        try:
            return await client.speak(lines, voice)
        except httpx.HTTPStatusError as exc:
            if voice is None or exc.response.status_code != httpx.codes.BAD_REQUEST:
                raise
            log.warning("short_voice_refused", voice=voice)
            return await client.speak(lines, None)
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("short_voice_failed", error=type(exc).__name__)
        return silent(lines)
