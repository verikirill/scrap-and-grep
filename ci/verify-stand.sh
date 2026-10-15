#!/bin/sh
# The path the jury walks, on the stand at STAND_URL: scripts/smoke.py builds
# and exports a digest, registers a reader with a resume and deletes what it
# made.
set -eu
cd "$(dirname "$0")/.."

exec uv run --script scripts/smoke.py "${STAND_URL:?}"
