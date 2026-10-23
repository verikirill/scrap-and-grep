#!/bin/sh
# The backend: ruff, the ruff formatter, mypy in strict mode and the check of
# the saved issues.
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
# The saved issues under examples/: one vulnerability per entry, advice that
# agrees with the fix, no ids or versions for management.
uv run --no-sync python "$root/scripts/check_examples.py" "$root/examples"
# Every number of the deck stands in the documents its slide cites.
uv run --no-sync python "$root/scripts/check_deck.py" "$root/docs/presentation/slides.html"
