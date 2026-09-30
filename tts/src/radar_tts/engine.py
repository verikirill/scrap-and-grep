"""Qwen3-TTS behind a lock: loaded on the first request, unloaded when idle.

The GPU is shared with the language model of the digests, so the voice model
holds its memory only while videos are being made (TTS_KEEP_ALIVE_SECONDS).
"""

import asyncio
import gc
import io
import logging
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import soundfile as sf
import torch

log = logging.getLogger("radar_tts")

# Loudness of every line, so a quiet sentence does not follow a loud one.
TARGET_RMS = 0.08
PEAK_LIMIT = 0.95
# Silence detection: 20 ms frames, quieter than 3 % of the loudest frame.
FRAME_MS = 20
SILENCE_SHARE = 0.03
KEEP_EDGE_MS = 40
LEAD_IN_MS = 150


class UnknownSpeaker(ValueError):
    """The requested speaker is not one of the model's voices."""


@dataclass(frozen=True, slots=True)
class Config:
    model: str
    speaker: str
    # Style instruction; the 0.6B models ignore it.
    instruct: str
    device: str
    keep_alive_seconds: float


@dataclass(frozen=True, slots=True)
class Speech:
    voice: str
    sample_rate: int
    segments: list[tuple[int, int]]
    wav: bytes


def pick_device(requested: str) -> str:
    if requested != "auto":
        return requested
    return "cuda:0" if torch.cuda.is_available() else "cpu"


def trim(wave: np.ndarray, sample_rate: int) -> np.ndarray:
    """Cut the silence before and after the speech, keeping a short edge."""
    frame = max(1, sample_rate * FRAME_MS // 1000)
    count = len(wave) // frame
    if count == 0:
        return wave
    energy = np.sqrt(np.mean(wave[: count * frame].reshape(count, frame) ** 2, axis=1))
    loud = np.flatnonzero(energy > energy.max() * SILENCE_SHARE)
    if loud.size == 0:
        return wave
    edge = sample_rate * KEEP_EDGE_MS // 1000
    start = max(0, int(loud[0]) * frame - edge)
    end = min(len(wave), (int(loud[-1]) + 1) * frame + edge)
    return wave[start:end]


def level(wave: np.ndarray) -> np.ndarray:
    """Bring a line to the common loudness without clipping its peaks."""
    rms = float(np.sqrt(np.mean(wave**2))) if wave.size else 0.0
    if rms == 0.0:
        return wave
    gain = TARGET_RMS / rms
    peak = float(np.max(np.abs(wave))) * gain
    if peak > PEAK_LIMIT:
        gain *= PEAK_LIMIT / peak
    return (wave * gain).astype(np.float32)


def assemble(
    waves: list[np.ndarray], sample_rate: int, gap_ms: int
) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """Join the lines with pauses and report where each one sits, in ms."""
    gap = np.zeros(sample_rate * gap_ms // 1000, dtype=np.float32)
    parts: list[np.ndarray] = [np.zeros(sample_rate * LEAD_IN_MS // 1000, dtype=np.float32)]
    segments = []
    at = len(parts[0])
    for index, wave in enumerate(waves):
        if index:
            parts.append(gap)
            at += len(gap)
        segments.append((at * 1000 // sample_rate, (at + len(wave)) * 1000 // sample_rate))
        parts.append(wave)
        at += len(wave)
    return np.concatenate(parts), segments


def encode_wav(wave: np.ndarray, sample_rate: int) -> bytes:
    buffer = io.BytesIO()
    sf.write(buffer, wave, sample_rate, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


class Engine:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.device = pick_device(config.device)
        self._model: Any = None
        self._lock = asyncio.Lock()
        self._last_used = time.monotonic()

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def _load(self) -> Any:
        if self._model is None:
            from qwen_tts import Qwen3TTSModel

            started = time.perf_counter()
            on_gpu = self.device.startswith("cuda")
            self._model = Qwen3TTSModel.from_pretrained(
                self.config.model,
                device_map=self.device,
                dtype=torch.bfloat16 if on_gpu else torch.float32,
                attn_implementation="sdpa",
            )
            log.info(
                "model_loaded %s on %s in %.1fs",
                self.config.model,
                self.device,
                time.perf_counter() - started,
            )
        return self._model

    def _unload(self) -> None:
        self._model = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        log.info("model_unloaded")

    def _generate_batch(
        self, model: Any, sentences: list[str], language: str, speaker: str
    ) -> tuple[list[Any], int]:
        with torch.inference_mode():
            if model.model.tts_model_type == "voice_design":
                waves, sample_rate = model.generate_voice_design(
                    text=sentences, language=language, instruct=self.config.instruct
                )
            else:
                waves, sample_rate = model.generate_custom_voice(
                    text=sentences,
                    language=language,
                    speaker=speaker,
                    instruct=self.config.instruct or None,
                )
        return list(waves), int(sample_rate)

    def _generate(
        self, sentences: list[str], language: str, speaker: str
    ) -> tuple[list[np.ndarray], int]:
        model = self._load()
        is_custom = model.model.tts_model_type != "voice_design"
        known = (
            {name.lower() for name in model.get_supported_speakers() or []} if is_custom else set()
        )
        if is_custom and speaker.lower() not in known:
            raise UnknownSpeaker(f"unknown speaker {speaker!r}; known: {sorted(known)}")
        try:
            waves, sample_rate = self._generate_batch(model, sentences, language, speaker)
        except torch.OutOfMemoryError:
            # The card is shared with the language model of the digests. One
            # line at a time needs a fraction of the memory of the batch.
            torch.cuda.empty_cache()
            log.warning("out_of_memory: generating %d lines one by one", len(sentences))
            waves, sample_rate = [], 0
            for sentence in sentences:
                one, sample_rate = self._generate_batch(model, [sentence], language, speaker)
                waves.extend(one)
        return [np.asarray(wave, dtype=np.float32) for wave in waves], sample_rate

    @staticmethod
    def _finish(waves: list[np.ndarray], sample_rate: int, voice: str, gap_ms: int) -> Speech:
        lines = [level(trim(wave, sample_rate)) for wave in waves]
        audio, segments = assemble(lines, sample_rate, gap_ms)
        return Speech(
            voice=voice,
            sample_rate=sample_rate,
            segments=segments,
            wav=encode_wav(audio, sample_rate),
        )

    async def speak(
        self, sentences: list[str], *, language: str, speaker: str | None, gap_ms: int
    ) -> Speech:
        voice = speaker or self.config.speaker
        async with self._lock:
            work = asyncio.ensure_future(
                asyncio.to_thread(self._generate, sentences, language, voice)
            )
            try:
                waves, sample_rate = await asyncio.shield(work)
            except asyncio.CancelledError:
                # The caller gave up, but a thread cannot be stopped. The lock
                # stays taken until it ends, so the next request does not run
                # the same model at the same time, and the idle unloader does
                # not pull it from under the thread.
                await asyncio.wait({work})
                raise
            finally:
                self._last_used = time.monotonic()
        # Trimming and encoding take a moment; the health check must not wait.
        return await asyncio.to_thread(self._finish, waves, sample_rate, voice, gap_ms)

    async def unload_when_idle(self) -> None:
        """Free the GPU after TTS_KEEP_ALIVE_SECONDS without requests."""
        period = max(1.0, min(30.0, self.config.keep_alive_seconds))
        while True:
            await asyncio.sleep(period)
            try:
                if not self._is_idle():
                    continue
                async with self._lock:
                    # A request may have come in while the lock was being taken.
                    if self._is_idle():
                        await asyncio.to_thread(self._unload)
            except Exception:
                # One failed unload must not stop the loop for good: the GPU
                # would then stay taken until the service restarts.
                log.exception("unload_failed")

    def _is_idle(self) -> bool:
        idle = time.monotonic() - self._last_used
        return self._model is not None and idle >= self.config.keep_alive_seconds
