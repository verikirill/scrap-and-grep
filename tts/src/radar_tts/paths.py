"""Where the models live on disk."""

import json
import os
from pathlib import Path

from huggingface_hub import hf_hub_download, snapshot_download


def _offline() -> bool:
    return bool(os.environ.get("HF_HUB_OFFLINE"))


def model_path(model: str) -> str:
    """A local directory for the model, downloading it only when allowed.

    transformers 4.57.3, which qwen-tts pins, asks the Hub about a repo id
    while loading the tokenizer even with HF_HUB_OFFLINE set, and fails in a
    container without network. A local path it takes as it is.
    """
    if os.path.isdir(model):
        return model
    return snapshot_download(model, local_files_only=_offline())


def model_kind(model: str) -> str | None:
    """The tts_model_type of a Qwen3-TTS model ("base", "custom_voice",
    "voice_design"), read from its config.json without loading the weights.
    None when the config cannot be found."""
    try:
        if os.path.isdir(model):
            config = Path(model) / "config.json"
        else:
            config = Path(hf_hub_download(model, "config.json", local_files_only=_offline()))
        data = json.loads(config.read_text("utf-8"))
    except (OSError, ValueError):
        # huggingface_hub reports a missing repo or file as OSError or
        # ValueError subclasses, depending on whether it went online.
        return None
    kind = data.get("tts_model_type") if isinstance(data, dict) else None
    return kind if isinstance(kind, str) else None
