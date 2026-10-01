"""Download the models at image build time, so the service runs offline:
the voice model and the Whisper that checks what it said."""

import os

from huggingface_hub import snapshot_download

DEFAULT_CHECK_MODEL = "Systran/faster-whisper-base"


def main() -> None:
    models = [
        os.environ.get("TTS_MODEL") or "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
        os.environ.get("TTS_CHECK_MODEL") or DEFAULT_CHECK_MODEL,
    ]
    for model in models:
        if model != "off":
            print(f"{model} -> {snapshot_download(model)}")  # noqa: T201


if __name__ == "__main__":
    main()
