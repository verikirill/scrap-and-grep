"""Make the voices to clone: Qwen3-TTS VoiceDesign speaks the reference text
in each described voice, three takes each, and the take Whisper hears most
correctly is kept in voices/.

    uv run scripts/design_voices.py

Needs an NVIDIA GPU with about 6 GB free and downloads the 1.7B VoiceDesign
model (4.3 GB) the first time. The voices are synthetic: none of them is a
recording of a real person.
"""

import json
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import torchaudio
from faster_whisper import WhisperModel
from qwen_tts import Qwen3TTSModel

from radar_tts.check import error_rate

VOICES_DIR = Path(__file__).resolve().parents[1] / "voices"
TAKES = 3

DESIGNS = {
    "anchor": (
        "Мужской голос, около 35 лет, ведущий новостей на радио. Говорит по-русски без "
        "акцента, уверенно и чётко, в среднем темпе, с деловой интонацией."
    ),
    "presenter": (
        "Женский голос, около 30 лет, ведущая технологического канала. Говорит по-русски без "
        "акцента, энергично и дружелюбно, чуть быстрее обычного, с живой интонацией."
    ),
    "blogger": (
        "Мужской голос, около 25 лет, автор коротких видео. Говорит по-русски без акцента, "
        "очень энергично и быстро, с яркими эмоциями, как в TikTok."
    ),
    "analyst": (
        "Женский голос, около 40 лет, аналитик по кибербезопасности. Говорит по-русски без "
        "акцента, спокойно, размеренно и уверенно."
    ),
}


def main() -> None:
    listing = json.loads((VOICES_DIR / "voices.json").read_text("utf-8"))
    asr = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
    model = Qwen3TTSModel.from_pretrained(
        "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
        device_map="cuda:0",
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
    )
    for entry in listing:
        best: tuple[float, np.ndarray, int] | None = None
        for _ in range(TAKES):
            waves, rate = model.generate_voice_design(
                text=[entry["text"]], language=["Russian"], instruct=[DESIGNS[entry["id"]]]
            )
            audio = torchaudio.functional.resample(torch.from_numpy(waves[0]), rate, 16000)
            segments, info = asr.transcribe(audio.numpy(), beam_size=5)
            heard = " ".join(segment.text for segment in segments)
            rate_of_errors = error_rate(entry["text"], heard)
            if info.language == "ru" and (best is None or rate_of_errors < best[0]):
                best = (rate_of_errors, waves[0], rate)
        if best is None:
            raise RuntimeError(f"no Russian take for {entry['id']}")
        sf.write(VOICES_DIR / entry["file"], best[1], best[2], subtype="PCM_16")
        print(f"{entry['id']}: error rate {best[0]:.3f}")  # noqa: T201


if __name__ == "__main__":
    main()
