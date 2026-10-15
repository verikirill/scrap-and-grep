#!/bin/sh
# docker-compose.yml with every override in the combinations the docs give,
# every profile on: `docker compose config` reads and checks them all.
set -eu
cd "$(dirname "$0")/.."

for extra in "" "-f docker-compose.dev.yml" "-f docker-compose.gpu.yml" \
    "-f docker-compose.vllm.yml" "-f docker-compose.airgap.yml" \
    "-f docker-compose.gpu.yml -f docker-compose.vllm.yml -f docker-compose.airgap.yml"; do
  echo "docker-compose.yml ${extra:-alone}, every profile"
  # shellcheck disable=SC2086 # $extra holds whole -f options
  docker compose -f docker-compose.yml $extra --profile '*' config --quiet
done
