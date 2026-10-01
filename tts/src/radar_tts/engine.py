"""Qwen3-TTS behind a lock: loaded on the first request, unloaded when idle.

The GPU is shared with the language model of the digests, so the voice model
holds its memory only while videos are being made (TTS_KEEP_ALIVE_SECONDS).
"""

import asyncio
import gc
import io
import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
import torch

from radar_tts.check import Checker, CheckerUnavailable
from radar_tts.paths import model_path

log = logging.getLogger("radar_tts")

# A line whose transcript differs from its text by more than this share of
# characters is generated again (check.py has the measurements).
CHECK_THRESHOLD = 0.45
CHECK_RETRIES = 2
# Time all the regenerations of one request may take. A clean short needs
# none; the budget keeps a request with many bad lines inside the caller's
# timeout (RADAR_TTS_TIMEOUT_SECONDS, 300 s).
CHECK_BUDGET_SECONDS = 90.0

VOICE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")

# Loudness of every line, so a quiet sentence does not follow a loud one.
TARGET_RMS = 0.08
PEAK_LIMIT = 0.95
# Silence detection: 20 ms frames, quieter than 3 % of the loudest frame.
FRAME_MS = 20
SILENCE_SHARE = 0.03
KEEP_EDGE_MS = 40
LEAD_IN_MS = 150


class UnknownSpeaker(ValueError):
    """The requested voice is not one this service can speak with."""


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


@dataclass(frozen=True, slots=True)
class Voice:
    """A voice to clone: a clip of it and what is said in the clip."""

    id: str
    title: str
    audio: Path
    text: str


def load_voices(directory: Path) -> dict[str, Voice]:
    """Voices listed in voices.json next to their clips; none if the file is absent."""
    listing = directory / "voices.json"
    if not listing.is_file():
        return {}
    voices = {}
    for entry in json.loads(listing.read_text("utf-8")):
        voice = Voice(entry["id"], entry["title"], directory / entry["file"], entry["text"])
        if not VOICE_ID_RE.fullmatch(voice.id):
            raise ValueError(f"voice id {voice.id!r}: use 1-40 Latin letters, digits, _ or -")
        if not voice.audio.is_file():
            raise FileNotFoundError(f"voice {voice.id}: {voice.audio} is missing")
        voices[voice.id] = voice
    return voices


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
    def __init__(
        self,
        config: Config,
        voices: dict[str, Voice],
        checker: Checker | None = None,
        kind: str | None = None,
    ) -> None:
        """kind is the model's tts_model_type (paths.model_kind), known
        before the weights are loaded."""
        if kind == "base" and config.speaker not in voices:
            # A Base model has no voice of its own: without a clip to clone
            # every request would fail, so the service does not start.
            raise ValueError(
                f"{config.model} clones voices; default {config.speaker!r} is not among "
                f"{sorted(voices) or 'the voices in TTS_VOICES_DIR (none found)'}"
            )
        self.config = config
        self.kind = kind
        self.device = pick_device(config.device)
        self.voices = voices
        self._checker = checker
        self._model: Any = None
        # Clone prompts are computed once per voice and model load.
        self._prompts: dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._last_used = time.monotonic()

    @property
    def loaded(self) -> bool:
        return self._model is not None

    @property
    def clones_voices(self) -> bool:
        """The model speaks with the listed voices, so there is a choice."""
        return self.kind == "base" and bool(self.voices)

    def _load(self) -> Any:
        if self._model is None:
            from qwen_tts import Qwen3TTSModel

            started = time.perf_counter()
            on_gpu = self.device.startswith("cuda")
            self._model = Qwen3TTSModel.from_pretrained(
                model_path(self.config.model),
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
        self._prompts.clear()
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        log.info("model_unloaded")

    def _validate(self, model: Any, voice: str) -> None:
        kind = model.model.tts_model_type
        if kind == "base" and voice not in self.voices:
            raise UnknownSpeaker(f"unknown voice {voice!r}; known: {sorted(self.voices)}")
        if kind == "custom_voice":
            known = {name.lower() for name in model.get_supported_speakers() or []}
            if voice.lower() not in known:
                raise UnknownSpeaker(f"unknown speaker {voice!r}; known: {sorted(known)}")

    def _prompt(self, model: Any, voice: str) -> Any:
        if voice not in self._prompts:
            clip = self.voices[voice]
            self._prompts[voice] = model.create_voice_clone_prompt(
                ref_audio=str(clip.audio), ref_text=clip.text
            )
        return self._prompts[voice]

    def _generate_batch(
        self, model: Any, sentences: list[str], language: str, voice: str
    ) -> tuple[list[Any], int]:
        with torch.inference_mode():
            kind = model.model.tts_model_type
            if kind == "base":
                waves, sample_rate = model.generate_voice_clone(
                    text=sentences, language=language, voice_clone_prompt=self._prompt(model, voice)
                )
            elif kind == "voice_design":
                waves, sample_rate = model.generate_voice_design(
                    text=sentences, language=language, instruct=self.config.instruct
                )
            else:
                waves, sample_rate = model.generate_custom_voice(
                    text=sentences,
                    language=language,
                    speaker=voice,
                    instruct=self.config.instruct or None,
                )
        return [np.asarray(wave, dtype=np.float32) for wave in waves], int(sample_rate)

    def _generate_all(
        self, model: Any, sentences: list[str], language: str, voice: str
    ) -> tuple[list[np.ndarray], int]:
        """All lines in one batch, or in halves when the card runs out of memory.

        The card is shared with the language model of the digests. A batch is
        several times faster than single lines (0.70 s of generation per second
        of speech for six lines, 2.80 for one at a time), but a clone decodes
        its reference clip with every line: six lines peak at 6.2 GB, three at
        4.1 GB, one at 2.8 GB (docs/DECISIONS.md).
        """
        try:
            return self._generate_batch(model, sentences, language, voice)
        except torch.OutOfMemoryError:
            if len(sentences) == 1:
                raise
            log.warning("out_of_memory: splitting a batch of %d lines", len(sentences))
        # Outside the handler, so the tensors of the failed batch are freed first.
        torch.cuda.empty_cache()
        half = (len(sentences) + 1) // 2
        first, sample_rate = self._generate_all(model, sentences[:half], language, voice)
        second, _ = self._generate_all(model, sentences[half:], language, voice)
        return first + second, sample_rate

    def _checked(
        self,
        model: Any,
        waves: list[np.ndarray],
        sample_rate: int,
        sentences: list[str],
        language: str,
        voice: str,
    ) -> list[np.ndarray]:
        """Lines that do not say what they should are generated again; the
        take closest to the text is kept.

        The check only improves the narration: if Whisper fails, the lines
        are kept as generated, and regeneration stops when its time budget
        is spent."""
        checker = self._checker
        if checker is None:
            return waves
        kept = list(waves)
        deadline = time.monotonic() + CHECK_BUDGET_SECONDS
        try:
            for index, sentence in enumerate(sentences):
                if time.monotonic() >= deadline:
                    log.warning("check_budget_spent: %d lines unchecked", len(sentences) - index)
                    break
                best = checker.error_rate(kept[index], sample_rate, sentence)
                attempts = 0
                while (
                    best > CHECK_THRESHOLD
                    and attempts < CHECK_RETRIES
                    and time.monotonic() < deadline
                ):
                    attempts += 1
                    (take,), _ = self._generate_batch(model, [sentence], language, voice)
                    rate = checker.error_rate(take, sample_rate, sentence)
                    if rate < best:
                        kept[index], best = take, rate
                if attempts or best > CHECK_THRESHOLD:
                    log.warning(
                        "line_regenerated index=%d attempts=%d error_rate=%.2f",
                        index,
                        attempts,
                        best,
                    )
        except CheckerUnavailable as exc:
            log.warning("check_skipped: %s", exc)
        except torch.OutOfMemoryError:
            log.warning("out_of_memory: the remaining lines are kept unchecked")
        except Exception:
            log.exception("check_failed: the remaining lines are kept unchecked")
        return kept

    def _generate(
        self, sentences: list[str], language: str, voice: str
    ) -> tuple[list[np.ndarray], int]:
        model = self._load()
        self._validate(model, voice)
        try:
            waves, sample_rate = self._generate_all(model, sentences, language, voice)
            return self._checked(model, waves, sample_rate, sentences, language, voice), sample_rate
        finally:
            # The weights stay loaded until the idle unload; the memory the
            # batch took goes back to the card for the language model.
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

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
