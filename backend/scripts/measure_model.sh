#!/usr/bin/env bash
# One run of the comparison of models (examples/models) on the model the stack
# runs now, with the hardware it ran on. From the repository root:
#
#   backend/scripts/measure_model.sh qwen3.6-35b-a3b
#
# The stack runs with the model set in .env (README, «Быстрый запуск»). The
# answers are cached in a Valkey database of their own, emptied first, so each
# model builds the digests from scratch. Writes to examples/models:
#   <name>.json           both digests: time, tokens, speed, memory of Ollama
#   <name>.dataset.json   the organizers' 21 examples through the same steps
#   <name>.hardware.json  card, driver, peak video memory, CPU, memory, Ollama
# Then `uv run scripts/model_report.py examples/models` puts them in the tables.
set -euo pipefail
# Git Bash on Windows would turn /tmp inside the container into a Windows path.
export MSYS_NO_PATHCONV=1

name=${1:?usage: backend/scripts/measure_model.sh <name, e.g. qwen3.6-35b-a3b>}
out=examples/models
cache=redis://valkey:6379/7
api=$(docker compose ps -q api | head -n 1)
valkey=$(docker compose ps -q valkey)
[ -n "$api" ] && [ -n "$valkey" ] || { echo "the stack is not running: no api or valkey" >&2; exit 1; }

docker exec "$valkey" valkey-cli -n 7 flushdb >/dev/null

# Video memory every half second while the digests are built.
vram=$(mktemp)
gpu=false
if command -v nvidia-smi >/dev/null 2>&1; then
  gpu=true
  nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -lms 500 >"$vram" &
  poll=$!
  trap 'kill "$poll" 2>/dev/null || true; rm -f "$vram"' EXIT
fi

started=$(date +%s)
docker exec -i -e RADAR_CACHE_URL=$cache "$api" python - <backend/scripts/model_compare.py
docker exec "$api" cat /tmp/model_compare.json >"$out/$name.json"
docker exec -i "$api" sh -c 'cat > /tmp/dataset.json' <docs/task/dataset_v4.0.json
docker exec -i -e RADAR_CACHE_URL=$cache "$api" python - <backend/scripts/dataset_run.py
docker exec "$api" cat /tmp/dataset_run.json >"$out/$name.dataset.json"
finished=$(date +%s)

if $gpu; then
  kill "$poll" 2>/dev/null || true
  peak=$(sort -n "$vram" | tail -n 1 | tr -d ' \r')
  card=$(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader | head -n 1 | tr -d '\r')
else
  peak=null
  card="no NVIDIA card"
fi
case "$(uname -s)" in
  MINGW* | MSYS* | CYGWIN*)
    cpu=$(powershell -NoProfile -Command '(Get-CimInstance Win32_Processor).Name.Trim()' | tr -d '\r')
    ram=$(powershell -NoProfile -Command '[math]::Round((Get-CimInstance Win32_PhysicalMemory | Measure-Object Capacity -Sum).Sum / 1GB)' | tr -d '\r')
    ;;
  *)
    cpu=$(sed -n 's/^model name[[:space:]]*: //p' /proc/cpuinfo | head -n 1)
    ram=$(awk '/MemTotal/ { printf "%d", $2 / 1048576 + 0.5 }' /proc/meminfo)
    ;;
esac
docker_cpus=$(docker info --format '{{.NCPU}}')
docker_memory=$(docker info --format '{{.MemTotal}}' | awk '{ printf "%.1f", $1 / 1e9 }')
ollama=$(docker compose exec -T ollama ollama --version 2>/dev/null | sed -n 's/.*version is //p' | tr -d '\r' || true)

cat >"$out/$name.hardware.json" <<EOF
{
  "date": "$(date +%F)",
  "card": "$card",
  "peak_vram_mib": $peak,
  "cpu": "$cpu",
  "ram_gb": ${ram:-null},
  "docker_cpus": $docker_cpus,
  "docker_memory_gb": $docker_memory,
  "ollama": "${ollama:-not in the stack}",
  "run_seconds": $((finished - started))
}
EOF
cat "$out/$name.hardware.json"
