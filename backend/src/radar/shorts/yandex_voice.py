"""The narration in Yandex SpeechKit: the same lines, timing and WAV as the
voice service gives, from Yandex Cloud instead of a GPU in the stack.

SpeechKit API v3 speaks one text per request, and at most about 250
characters of it: a longer line is cut at sentence ends, then at words, and
its parts follow one another without a pause. Lines are voiced a few at a
time and joined with the same pause the voice service puts between them.
"""

import asyncio
import base64
import io
import json
import wave

import httpx
from pydantic import SecretStr

from radar.logging import get_logger
from radar.shorts.model import Narration, Segment
from radar.shorts.speech import spoken
from radar.shorts.voice import GAP_MS, VoiceOption
from radar.text import split_sentences

log = get_logger(__name__)

URL = "https://tts.api.cloud.yandex.net/tts/v3/utteranceSynthesis"
SAMPLE_RATE = 24_000
_SAMPLE_WIDTH = 2
# Measured on 15 October 2026: 243 characters are spoken, 487 are "Too long text".
MAX_CHARS = 240
# Requests in flight at once for one narration.
CONCURRENCY = 4

# The Russian voices of SpeechKit, each heard read back word for word by its
# recognition on a line of a digest (15 October 2026).
VOICES: dict[str, str] = {
    "alena": "Алёна",
    "filipp": "Филипп",
    "ermil": "Ермил",
    "jane": "Джейн",
    "omazh": "Омаж",
    "zahar": "Захар",
    "dasha": "Даша",
    "masha": "Маша",
    "marina": "Марина",
    "alexander": "Александр",
    "kirill": "Кирилл",
    "anton": "Антон",
}
DEFAULT_VOICE = "alena"


def _by_words(text: str, limit: int) -> list[str]:
    parts: list[str] = []
    for word in text.split():
        word = word[:limit]
        if parts and len(parts[-1]) + 1 + len(word) <= limit:
            parts[-1] = f"{parts[-1]} {word}"
        else:
            parts.append(word)
    return parts


def pieces(line: str, limit: int = MAX_CHARS) -> list[str]:
    """The line in parts SpeechKit takes: as many whole sentences as fit,
    a sentence too long alone cut at words in parts of its own."""
    parts: list[str] = []
    for sentence in split_sentences(line):
        if len(sentence) > limit:
            parts.extend(_by_words(sentence, limit))
        elif parts and len(parts[-1]) + 1 + len(sentence) <= limit:
            parts[-1] = f"{parts[-1]} {sentence}"
        else:
            parts.append(sentence)
    return parts


def _audio(body: str) -> bytes:
    """The PCM of a streamed answer: one JSON object per line, audio in chunks."""
    audio = bytearray()
    for line in body.splitlines():
        if not line.strip():
            continue
        chunk = json.loads(line).get("result", {}).get("audioChunk")
        if chunk:
            audio += base64.b64decode(chunk["data"])
    if not audio:
        raise ValueError("SpeechKit returned no audio")
    return bytes(audio)


def _wav(pcm: bytes) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(_SAMPLE_WIDTH)
        writer.setframerate(SAMPLE_RATE)
        writer.writeframes(pcm)
    return out.getvalue()


def _ms(pcm: bytes) -> int:
    return len(pcm) * 1000 // (SAMPLE_RATE * _SAMPLE_WIDTH)


class YandexVoiceClient:
    def __init__(
        self,
        api_key: SecretStr,
        folder: str,
        *,
        timeout: float,
        speaker: str = "",
        url: str = URL,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._headers = {"Authorization": f"Api-Key {api_key.get_secret_value()}"}
        if folder:
            self._headers["x-folder-id"] = folder
        self._timeout = httpx.Timeout(timeout, connect=10.0)
        self._default = speaker if speaker in VOICES else DEFAULT_VOICE
        self._url = url
        self._transport = transport

    async def voices(self) -> list[VoiceOption]:
        return [
            VoiceOption(id=voice, title=title, default=voice == self._default)
            for voice, title in VOICES.items()
        ]

    async def speak(self, lines: list[str], voice: str | None = None) -> Narration:
        # A voice SpeechKit does not have answers 403, not the voice service's
        # 400: a picked voice that is not on the list gives way here.
        if voice is not None and voice not in VOICES:
            log.warning("yandex_voice_refused", voice=voice)
            voice = None
        chosen = voice or self._default
        slots = asyncio.Semaphore(CONCURRENCY)
        async with httpx.AsyncClient(
            timeout=self._timeout, transport=self._transport, headers=self._headers
        ) as client:

            async def say(text: str) -> bytes:
                payload = {
                    "text": text,
                    "hints": [{"voice": chosen}],
                    "outputAudioSpec": {
                        "rawAudio": {
                            "audioEncoding": "LINEAR16_PCM",
                            "sampleRateHertz": SAMPLE_RATE,
                        }
                    },
                }
                async with slots:
                    response = await client.post(self._url, json=payload)
                response.raise_for_status()
                return _audio(response.text)

            async def line_audio(line: str) -> bytes:
                texts = pieces(spoken(line))
                if not texts:
                    raise ValueError("a line with nothing to say")
                parts = await asyncio.gather(*(say(text) for text in texts))
                return b"".join(parts)

            voiced = await asyncio.gather(*(line_audio(line) for line in lines))

        gap = b"\x00" * (SAMPLE_RATE * GAP_MS // 1000) * _SAMPLE_WIDTH
        pcm = bytearray()
        segments: list[Segment] = []
        for index, audio in enumerate(voiced):
            if index:
                pcm += gap
            start = _ms(bytes(pcm))
            pcm += audio
            segments.append(Segment(start, _ms(bytes(pcm))))
        return Narration(segments=tuple(segments), audio=_wav(bytes(pcm)), voice=f"yandex:{chosen}")
