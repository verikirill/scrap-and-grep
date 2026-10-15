#!/bin/sh
# The backend: ruff, the ruff formatter and mypy in strict mode.
#
# CODE_QUALITY_REPORT  a path from the repository root; when set, the ruff
#                      findings also go there for the Code Quality widget of
#                      a GitLab merge request
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
cd "$root/backend"

uv sync --locked
if [ -n "${CODE_QUALITY_REPORT:-}" ]; then
  uv run --no-sync ruff check --exit-zero --output-format=gitlab \
    --output-file="$root/$CODE_QUALITY_REPORT" .
fi
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync mypy
