"""Does a generated line say what it should? Whisper listens and compares.

Qwen3-TTS samples its speech, and once in a while a line collapses into a
language that does not exist: in one short the whole first news item came
out as gibberish while the lines around it were clean. A small Whisper on
the CPU transcribes each line; a line whose character error rate against
its text is above the threshold is generated again.

Measured on that short (whisper base, CPU, 4 threads): the broken line had a
CER of 0.70, the clean ones 0.00-0.29 (a "4" heard for "четыре"), about a
second per line.
"""

import logging
import os
import re
import threading
from typing import Any

import numpy as np
import torch
import torchaudio

from radar_tts.paths import model_path

log = logging.getLogger("radar_tts")

WHISPER_RATE = 16_000
_PUNCTUATION_RE = re.compile(r"[^\w\s]")
_SPACE_RE = re.compile(r"\s+")
# Latin names, numbers and identifiers are written one way in the script and
# heard another ("Siemens" as "Сименс", "7.8" as "семь и восемь"). In the text
# each run of them becomes a wildcard that matches whatever was heard in its
# place, so only the Russian words are compared.
_FOREIGN_RE = re.compile(r"[a-z0-9]")
WILDCARD = "*"
# A line with fewer Russian characters than this has nothing to check it by.
MIN_CHECKABLE = 12


def normalize(text: str) -> str:
    text = text.lower().replace("ё", "е")
    return _SPACE_RE.sub(" ", _PUNCTUATION_RE.sub(" ", text)).strip()


def reference(text: str) -> str:
    """The text as it is checked: runs of foreign words become one wildcard."""
    words: list[str] = []
    for word in normalize(text).split():
        if not _FOREIGN_RE.search(word):
            words.append(word)
        elif not words or words[-1] != WILDCARD:
            words.append(WILDCARD)
    return " ".join(words)


def error_rate(expected: str, heard: str) -> float:
    """Character error rate over the Russian words: edits needed to turn what
    was heard into the text, per character of the text."""
    wanted_text, hypothesis = reference(expected), normalize(heard)
    checked = len(wanted_text) - wanted_text.count(WILDCARD)
    if checked < MIN_CHECKABLE:
        return 0.0
    previous = list(range(len(hypothesis) + 1))
    for wanted in wanted_text:
        if wanted == WILDCARD:
            # Takes any number of heard characters for free.
            current = [previous[0]]
            for col in range(1, len(hypothesis) + 1):
                current.append(min(previous[col], current[col - 1]))
        else:
            current = [previous[0] + 1]
            for col, got in enumerate(hypothesis, start=1):
                current.append(
                    min(
                        previous[col] + 1,
                        current[col - 1] + 1,
                        previous[col - 1] + (wanted != got),
                    )
                )
        previous = current
    return previous[-1] / checked


class CheckerUnavailable(RuntimeError):
    """Whisper could not be loaded; the lines go unchecked."""


class Checker:
    """Whisper on the CPU, loaded on first use; the GPU is left to the voice."""

    def __init__(self, model: str, threads: int) -> None:
        self._model_name = model
        self._threads = threads
        self._model: Any = None
        self._failed = False
        self._lock = threading.Lock()

    def _load(self) -> Any:
        with self._lock:
            # A model that failed to load once is not looked for on every
            # request: offline it would fail the same way, online it could
            # hang each request on a download.
            if self._failed:
                raise CheckerUnavailable(f"{self._model_name} failed to load earlier")
            if self._model is None:
                from faster_whisper import WhisperModel

                try:
                    self._model = WhisperModel(
                        model_path(self._model_name),
                        device="cpu",
                        compute_type="int8",
                        cpu_threads=self._threads,
                    )
                except Exception as exc:
                    self._failed = True
                    raise CheckerUnavailable(f"{self._model_name}: {exc}") from exc
            return self._model

    def error_rate(self, wave: np.ndarray, sample_rate: int, text: str) -> float:
        mono = torch.from_numpy(np.asarray(wave, dtype=np.float32))
        audio = torchaudio.functional.resample(mono, sample_rate, WHISPER_RATE).numpy()
        segments, _ = self._load().transcribe(
            audio, language="ru", beam_size=1, condition_on_previous_text=False
        )
        return error_rate(text, " ".join(segment.text for segment in segments))


def checker_from_env() -> Checker | None:
    """TTS_CHECK_MODEL=off turns the check off."""
    model = os.environ.get("TTS_CHECK_MODEL") or "Systran/faster-whisper-base"
    if model == "off":
        return None
    return Checker(model, threads=int(os.environ.get("TTS_CHECK_THREADS") or 4))
