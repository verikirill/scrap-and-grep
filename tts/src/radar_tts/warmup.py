"""Download the voice model at image build time, so the service runs offline."""

import os

from huggingface_hub import snapshot_download


def main() -> None:
    model = os.environ.get("TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice")
    path = snapshot_download(model)
    print(f"{model} -> {path}")  # noqa: T201


if __name__ == "__main__":
    main()
