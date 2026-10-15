#!/bin/sh
# tts and docparser, the services built on PyTorch: ruff, the ruff formatter
# and locks that match their pyproject.toml.
set -eu
cd "$(dirname "$0")/.."

# Their locks are for Python 3.13, which uv fetches for the check.
export UV_PYTHON_DOWNLOADS=automatic
uvx ruff@0.16.9 check tts docparser
uvx ruff@0.16.9 format --check tts docparser
(cd tts && uv lock --check)
(cd docparser && uv lock --check)
