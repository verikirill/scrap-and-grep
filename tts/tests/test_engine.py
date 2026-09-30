"""Post-processing of the narration and the model lock; no model is loaded."""

import asyncio
import threading

import numpy as np
import pytest

from radar_tts.engine import (
    KEEP_EDGE_MS,
    LEAD_IN_MS,
    PEAK_LIMIT,
    TARGET_RMS,
    Config,
    Engine,
    assemble,
    level,
    trim,
)

RATE = 24_000


def tone(seconds: float, amplitude: float = 0.3) -> np.ndarray:
    t = np.arange(int(seconds * RATE)) / RATE
    return (amplitude * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


def silence(seconds: float) -> np.ndarray:
    return np.zeros(int(seconds * RATE), dtype=np.float32)


def test_silence_around_a_line_is_cut_but_the_edges_are_kept() -> None:
    speech = tone(1.0)
    wave = np.concatenate([silence(0.5), speech, silence(0.7)])

    trimmed = trim(wave, RATE)

    edge = RATE * KEEP_EDGE_MS // 1000
    assert len(speech) <= len(trimmed) <= len(speech) + 2 * edge + RATE // 25


def test_lines_come_out_equally_loud_without_clipping() -> None:
    quiet, loud = level(tone(1.0, 0.02)), level(tone(1.0, 0.9))
    spiky = level(np.concatenate([tone(1.0, 0.01), np.array([0.9], dtype=np.float32)]))

    for wave in (quiet, loud):
        assert np.sqrt(np.mean(wave**2)) == pytest.approx(TARGET_RMS, rel=0.01)
    # A single loud sample limits the gain instead of being clipped.
    assert np.max(np.abs(spiky)) <= PEAK_LIMIT + 1e-6


def test_segments_say_where_each_line_sits_in_the_joined_audio() -> None:
    audio, segments = assemble([tone(1.0), tone(0.5)], RATE, gap_ms=400)

    assert segments == [(LEAD_IN_MS, LEAD_IN_MS + 1000), (LEAD_IN_MS + 1400, LEAD_IN_MS + 1900)]
    assert len(audio) == RATE * (LEAD_IN_MS + 1900) // 1000


class SlowEngine(Engine):
    """Generation that runs until the test lets it finish."""

    def __init__(self) -> None:
        super().__init__(
            Config(model="none", speaker="Aiden", instruct="", device="cpu", keep_alive_seconds=60)
        )
        self.release = threading.Event()
        self.started = threading.Event()

    def _generate(
        self, sentences: list[str], language: str, speaker: str
    ) -> tuple[list[np.ndarray], int]:
        self.started.set()
        self.release.wait(timeout=5)
        return [tone(0.2) for _ in sentences], RATE


async def test_a_request_that_gave_up_keeps_the_model_until_its_thread_ends() -> None:
    engine = SlowEngine()
    request = asyncio.create_task(
        engine.speak(["Строка."], language="Russian", speaker=None, gap_ms=300)
    )
    await asyncio.to_thread(engine.started.wait, 5)

    request.cancel()
    await asyncio.sleep(0.05)
    # The caller is gone, the thread is not: nobody else may use the model.
    assert engine._lock.locked()

    engine.release.set()
    with pytest.raises(asyncio.CancelledError):
        await request
    assert not engine._lock.locked()


async def test_speech_reports_the_voice_and_one_segment_per_line() -> None:
    engine = SlowEngine()
    engine.release.set()

    speech = await engine.speak(["Раз.", "Два."], language="Russian", speaker="Serena", gap_ms=300)

    assert speech.voice == "Serena"
    assert len(speech.segments) == 2
    assert speech.wav[:4] == b"RIFF"
