#!/bin/sh
# The whole stack on Yandex AI Studio models, in the CI virtual machine: the
# images of this commit, Qwen3.6 for the writing, text-embeddings-v2 for the
# search and SpeechKit for the voice. scripts/smoke.py then walks the path of
# the jury on it: a digest, the exports, a short video, a resume, the feed and
# a company space whose team the model drafts. The stack goes away at the end.
#
# YANDEX_API_KEY  an API key of a service account with ai.languageModels.user
#                 and ai.speechkit-tts.user
# YANDEX_FOLDER   the folder id of the key
# SMOKE_VIDEO     true (the default) also starts the video service
set -eu
cd "$(dirname "$0")/.."

: "${YANDEX_API_KEY:?}" "${YANDEX_FOLDER:?}"
port=${WEB_PORT:-8080}
env_file=$(mktemp)
profiles=""
shorts_url=""
if [ "${SMOKE_VIDEO:-true}" = true ]; then
  profiles="--profile video"
  shorts_url=http://shorts:3000
fi

compose() {
  # shellcheck disable=SC2086  # the profile flags split on purpose
  docker compose -p ci-yandex --env-file "$env_file" -f docker-compose.yml $profiles "$@"
}
cleanup() {
  status=$?
  if [ "$status" -ne 0 ]; then
    compose ps || true
    compose logs --tail 80 api worker-digest migrate || true
  fi
  compose down -v --remove-orphans >/dev/null 2>&1 || true
  rm -f "$env_file"
  exit "$status"
}
trap cleanup EXIT

ai=https://ai.api.cloud.yandex.net/v1
# The key goes into a file only the runner reads, never onto a command line.
umask 077
# The video service asks for no more processors than the machine has.
cat >"$env_file" <<EOF
WEB_PORT=$port
SHORTS_CPUS=$(nproc)
RADAR_SHORTS_URL=$shorts_url
POSTGRES_PASSWORD=$(openssl rand -hex 16)
RADAR_SECRET_KEY=$(openssl rand -hex 32)
RADAR_LLM_PROVIDER=openai
RADAR_LLM_BASE_URL=$ai
RADAR_LLM_MODEL=gpt://$YANDEX_FOLDER/qwen3.6-35b-a3b/latest
RADAR_LLM_PROJECT=$YANDEX_FOLDER
RADAR_LLM_API_KEY=$YANDEX_API_KEY
RADAR_LLM_REASONING=off
RADAR_LLM_CONCURRENCY=2
RADAR_EMBEDDING_PROVIDER=openai
RADAR_EMBEDDING_BASE_URL=$ai
RADAR_EMBEDDING_MODEL=emb://$YANDEX_FOLDER/text-embeddings-v2-doc/latest
RADAR_EMBEDDING_QUERY_MODEL=emb://$YANDEX_FOLDER/text-embeddings-v2-query/latest
RADAR_EMBEDDING_PROJECT=$YANDEX_FOLDER
RADAR_EMBEDDING_API_KEY=$YANDEX_API_KEY
RADAR_TTS_PROVIDER=yandex
RADAR_TTS_API_KEY=$YANDEX_API_KEY
RADAR_TTS_FOLDER=$YANDEX_FOLDER
RADAR_TTS_VOICE=filipp
EOF

compose up -d --build
# The gateway answers once the API is up and the migrations are in.
deadline=$(($(date +%s) + 600))
until curl -fsS "http://localhost:$port/api/v1/meta" >/dev/null 2>&1; do
  if [ "$(date +%s)" -gt "$deadline" ]; then
    echo "the API did not come up in time" >&2
    exit 1
  fi
  sleep 10
done
# The snapshot of articles is embedded by the workers after the start: the
# digest needs them searchable, so the smoke waits until most are.
deadline=$(($(date +%s) + 900))
while :; do
  meta=$(curl -fsS "http://localhost:$port/api/v1/meta" || true)
  articles=$(printf '%s' "$meta" | sed -n 's/.*"articles": *\([0-9]*\).*/\1/p')
  embedded=$(printf '%s' "$meta" | sed -n 's/.*"embedded": *\([0-9]*\).*/\1/p')
  echo "articles=${articles:-?} embedded=${embedded:-?}"
  if [ -n "$articles" ] && [ "$articles" -gt 0 ] && [ "${embedded:-0}" -ge $((articles * 9 / 10)) ]; then
    break
  fi
  if [ "$(date +%s)" -gt "$deadline" ]; then
    echo "the articles were not embedded in time" >&2
    exit 1
  fi
  sleep 20
done

uv run --script scripts/smoke.py "http://localhost:$port"
