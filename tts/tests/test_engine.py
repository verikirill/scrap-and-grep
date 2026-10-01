"""Post-processing of the narration and the model lock; no model is loaded."""

import asyncio
import json
import threading
from pathlib import Path

import numpy as np
import pytest
import torch

from radar_tts import check as check_module
from radar_tts import engine as engine_module
from radar_tts.check import Checker, error_rate
from radar_tts.engine import (
    CHECK_THRESHOLD,
    KEEP_EDGE_MS,
    LEAD_IN_MS,
    PEAK_LIMIT,
    TARGET_RMS,
    Config,
    Engine,
    assemble,
    level,
    load_voices,
    trim,
)
from radar_tts.paths import model_kind

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
            Config(model="none", speaker="Aiden", instruct="", device="cpu", keep_alive_seconds=60),
            voices={},
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


def test_error_rate_ignores_case_and_punctuation_but_not_gibberish() -> None:
    text = "Компания закрыла уязвимость, обновитесь!"

    assert error_rate(text, "компания закрыла уязвимость обновитесь") == 0.0
    assert error_rate(text, "А кънагуери онли тиранетис налиќеќе") > CHECK_THRESHOLD


def test_names_and_numbers_may_be_heard_in_any_spelling() -> None:
    text = "Siemens оценила уязвимость CVE-2026-1234 в 9.8 балла."

    assert error_rate(text, "Сименс оценила уязвимость CVE 2026 1234 в 9,8 балла") == 0.0
    assert error_rate(text, "siemens оценила уязвимость си ви и в девять и восемь балла") == 0.0
    assert error_rate(text, "Сименс кънагуери онли тиранетис девять налиќеќе") > CHECK_THRESHOLD
    # Too little Russian to tell a good take from a bad one.
    assert error_rate("Patch Tuesday: 74 CVE в Windows", "что угодно") == 0.0


class FakeChecker:
    """Hands out error rates in order, as if Whisper had heard each take."""

    def __init__(self, rates: list[float]) -> None:
        self.rates = rates

    def error_rate(self, wave: np.ndarray, sample_rate: int, text: str) -> float:
        return self.rates.pop(0)


class BrokenChecker:
    """Whisper that fails, for instance because its model is missing."""

    def error_rate(self, wave: np.ndarray, sample_rate: int, text: str) -> float:
        raise RuntimeError("model.bin not found")


class TakesEngine(Engine):
    """Every generation returns a new take, numbered by its amplitude."""

    def __init__(self, checker: FakeChecker | BrokenChecker | Checker) -> None:
        super().__init__(
            Config(model="none", speaker="Aiden", instruct="", device="cpu", keep_alive_seconds=60),
            voices={},
            checker=checker,  # type: ignore[arg-type]
        )
        self.takes = 0

    def _generate_batch(
        self, model: object, sentences: list[str], language: str, voice: str
    ) -> tuple[list[np.ndarray], int]:
        waves = []
        for _ in sentences:
            self.takes += 1
            waves.append(np.full(10, self.takes, dtype=np.float32))
        return waves, RATE


def test_a_line_that_says_something_else_is_generated_again_and_the_best_take_kept() -> None:
    # Line one is clean; line two is broken, then worse, then close to the text.
    engine = TakesEngine(FakeChecker([0.05, 1.0, 1.1, 0.12]))

    waves, _ = engine._generate_all(None, ["Первая.", "Вторая."], "Russian", "Aiden")
    kept = engine._checked(None, waves, RATE, ["Первая.", "Вторая."], "Russian", "Aiden")

    assert engine.takes == 4
    assert kept[0][0] == 1
    # The third take of line two (the fourth generation overall) is the one kept.
    assert kept[1][0] == 4


def test_a_line_that_stays_broken_keeps_its_best_take_after_the_retries() -> None:
    engine = TakesEngine(FakeChecker([0.9, 0.7, 0.8]))

    waves, _ = engine._generate_all(None, ["Строка."], "Russian", "Aiden")
    kept = engine._checked(None, waves, RATE, ["Строка."], "Russian", "Aiden")

    assert engine.takes == 3
    assert kept[0][0] == 2


def test_a_failing_check_keeps_the_lines_as_generated() -> None:
    engine = TakesEngine(BrokenChecker())

    waves, _ = engine._generate_all(None, ["Первая.", "Вторая."], "Russian", "Aiden")
    kept = engine._checked(None, waves, RATE, ["Первая.", "Вторая."], "Russian", "Aiden")

    assert [wave[0] for wave in kept] == [1, 2]
    assert engine.takes == 2


class SmallCardEngine(TakesEngine):
    """A card that holds at most two lines at once."""

    def __init__(self) -> None:
        super().__init__(FakeChecker([]))
        self.batches: list[int] = []

    def _generate_batch(
        self, model: object, sentences: list[str], language: str, voice: str
    ) -> tuple[list[np.ndarray], int]:
        self.batches.append(len(sentences))
        if len(sentences) > 2:
            raise torch.OutOfMemoryError("CUDA out of memory")
        return super()._generate_batch(model, sentences, language, voice)


def test_a_batch_too_big_for_the_card_is_split_in_halves_keeping_the_order() -> None:
    engine = SmallCardEngine()
    lines = [f"Строка {number}." for number in range(6)]

    waves, _ = engine._generate_all(None, lines, "Russian", "Aiden")

    # 6 fails, 3 fails, then 2 + 1 for each half; never six single lines.
    assert engine.batches == [6, 3, 2, 1, 3, 2, 1]
    assert [wave[0] for wave in waves] == [1, 2, 3, 4, 5, 6]


def test_whisper_that_failed_to_load_is_not_loaded_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = []

    def missing(model: str) -> str:
        attempts.append(model)
        raise OSError("no such model")

    monkeypatch.setattr(check_module, "model_path", missing)
    checker = Checker("Systran/faster-whisper-base", threads=1)
    engine = TakesEngine(checker)  # type: ignore[arg-type]

    for _ in range(2):
        waves, _ = engine._generate_all(None, ["Строка."], "Russian", "Aiden")
        kept = engine._checked(None, waves, RATE, ["Строка."], "Russian", "Aiden")
        assert len(kept) == 1

    assert attempts == ["Systran/faster-whisper-base"]


def test_no_line_is_generated_again_once_the_time_budget_is_spent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(engine_module, "CHECK_BUDGET_SECONDS", 0.0)
    engine = TakesEngine(FakeChecker([1.0, 1.0]))

    waves, _ = engine._generate_all(None, ["Первая.", "Вторая."], "Russian", "Aiden")
    kept = engine._checked(None, waves, RATE, ["Первая.", "Вторая."], "Russian", "Aiden")

    assert engine.takes == 2
    assert [wave[0] for wave in kept] == [1, 2]


def write_voices(directory: Path, voice_id: str = "anchor") -> None:
    (directory / f"{voice_id}.wav").write_bytes(b"RIFF")
    listing = [
        {"id": voice_id, "title": "Ведущий", "file": f"{voice_id}.wav", "text": "Добрый день."}
    ]
    (directory / "voices.json").write_text(json.dumps(listing), "utf-8")


def test_voices_are_read_from_their_listing_and_a_missing_clip_is_an_error(tmp_path: Path) -> None:
    write_voices(tmp_path)

    voices = load_voices(tmp_path)

    assert voices["anchor"].title == "Ведущий"
    assert load_voices(tmp_path / "absent") == {}
    (tmp_path / "anchor.wav").unlink()
    with pytest.raises(FileNotFoundError):
        load_voices(tmp_path)


def test_a_voice_id_may_have_digits_but_not_spaces(tmp_path: Path) -> None:
    write_voices(tmp_path, "anchor-2")
    assert list(load_voices(tmp_path)) == ["anchor-2"]

    write_voices(tmp_path, "anchor 2")
    with pytest.raises(ValueError, match="voice id"):
        load_voices(tmp_path)


def test_a_base_model_without_its_default_voice_does_not_start(tmp_path: Path) -> None:
    write_voices(tmp_path)
    config = Config(
        model="Base", speaker="anchor", instruct="", device="cpu", keep_alive_seconds=60
    )

    assert Engine(config, load_voices(tmp_path), kind="base").clones_voices
    with pytest.raises(ValueError, match="clones voices"):
        Engine(config, {}, kind="base")
    # A model with built-in speakers offers no choice, whatever is in voices/.
    assert not Engine(config, load_voices(tmp_path), kind="custom_voice").clones_voices


def test_the_model_type_is_read_from_its_config(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text('{"tts_model_type": "base"}', "utf-8")

    assert model_kind(str(tmp_path)) == "base"
    assert model_kind(str(tmp_path / "absent")) is None
