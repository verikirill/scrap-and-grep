#!/bin/sh
# The headless browser service, its guard and its proxy: ruff, the ruff
# formatter, mypy and the tests. The tests that start Firefox itself run where
# camoufox is fetched, as in the image. Writes browser/junit.xml.
set -eu
cd "$(dirname "$0")/../browser"

uv sync --locked
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync mypy src
uv run --no-sync pytest -ra --junitxml=junit.xml
