#!/bin/sh
# The whole backend suite against real PostgreSQL with pgvector, Valkey and
# ClickHouse, with coverage. Writes backend/junit.xml and backend/coverage.xml
# (Cobertura).
#
# RADAR_TEST_ADMIN_DSN, RADAR_TEST_CACHE_URL, RADAR_TEST_CLICKHOUSE_URL
#   where the services are; the tests default to 127.0.0.1, the ports that
#   docker-compose.dev.yml publishes
set -eu
cd "$(dirname "$0")/../backend"

# LightGBM, the feed ranker, needs the OpenMP runtime: the backend image has
# it, a slim Debian image gets it here.
if command -v apt-get >/dev/null && ! ldconfig -p | grep -q libgomp.so.1; then
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends libgomp1 >/dev/null
fi

uv sync --locked

# A service that starts slowly is waited for, so that its tests run.
for url in "${RADAR_TEST_ADMIN_DSN:-postgresql://radar:radar@127.0.0.1:5432/postgres}" \
    "${RADAR_TEST_CACHE_URL:-redis://127.0.0.1:6379/15}" \
    "${RADAR_TEST_CLICKHOUSE_URL:-http://127.0.0.1:8123}"; do
  address=${url#*://}
  address=${address##*@}
  address=${address%%/*}
  timeout 90 bash -c "until (exec 3<>/dev/tcp/${address%:*}/${address##*:}) 2>/dev/null; do sleep 1; done" ||
    { echo "$address did not come up" >&2; exit 1; }
done

uv run --no-sync pytest -ra --junitxml=junit.xml \
  --cov=radar --cov-report=term --cov-report=xml:coverage.xml

# Integration tests skip when their service does not answer. Here such a skip
# fails the run: a dead service cannot pass for green.
if grep -oE '<skipped[^>]*message="[^"]*(not reachable|no Valkey)[^"]*"' junit.xml; then
  echo "integration tests were skipped: a service did not answer" >&2
  exit 1
fi
