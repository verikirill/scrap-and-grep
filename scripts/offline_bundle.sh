#!/usr/bin/env bash
# Delivery to a closed network: everything the stack needs, in a directory.
#
# On a machine with internet, from the repository root:
#   scripts/offline_bundle.sh save /path/to/bundle [profile...]
# The profiles are those of docker-compose.yml besides the core: ollama is
# always in, add docling, video, voice and so on if they are wanted there.
# The bundle holds:
#   radar-images.tar   every image of those profiles, built and pulled here
#   ollama-models.tar  the Ollama models: the embedder and the language model
#   radar-repo.tar     the repository at HEAD: compose files, configs, samples
#   SHA256SUMS
#   offline_bundle.sh  this script, to unpack it all on the other side
# The models are taken from RADAR_EMBEDDING_MODEL and RADAR_LLM_MODEL in the
# environment, then .env, then the defaults; missing ones are pulled first.
#
# On the target machine, with Docker and no internet:
#   bash /path/to/bundle/offline_bundle.sh load /path/to/bundle /srv/radar
# unpacks the repository to /srv/radar, loads the images and the models and
# prints the lines for .env. vLLM weights are not in the bundle: copy the
# Hugging Face cache directory and set VLLM_MODELS_DIR (README).
set -euo pipefail
# Git Bash on Windows would rewrite the container paths below.
export MSYS_NO_PATHCONV=1

die() { echo "offline_bundle: $*" >&2; exit 1; }
# A path Docker on this host understands: C:/... in Git Bash, /... elsewhere.
abs() { (cd "$1" && { pwd -W 2>/dev/null || pwd; }); }
setting() {
  local name=$1 fallback=$2 value=${!1:-}
  if [ -z "$value" ] && [ -f .env ]; then
    value=$(sed -n "s/^$name=//p" .env | tail -n 1 | tr -d '\r')
  fi
  echo "${value:-$fallback}"
}

save() {
  local dir=${1:?usage: offline_bundle.sh save <dir> [profile...]}
  shift
  [ -f docker-compose.yml ] || die "run from the repository root"
  mkdir -p "$dir"
  local profiles=(--profile ollama)
  for profile in "$@"; do profiles+=(--profile "$profile"); done

  echo "building and pulling the images of: ollama $*"
  docker compose "${profiles[@]}" build
  docker compose "${profiles[@]}" pull --ignore-buildable
  local images
  mapfile -t images < <(docker compose "${profiles[@]}" config --images | sort -u)
  echo "saving ${#images[@]} images"
  docker save -o "$dir/radar-images.tar" "${images[@]}"

  local embedder llm
  embedder=$(setting RADAR_EMBEDDING_MODEL embeddinggemma:300m)
  llm=$(setting RADAR_LLM_MODEL qwen3.6:35b-a3b)
  echo "exporting the Ollama models: $embedder $llm"
  docker volume create radar_ollama >/dev/null
  # The running stack's Ollama pulls what is missing; otherwise a server of
  # our own on the same volume does.
  local server
  server=$(docker compose ps -q ollama 2>/dev/null || true)
  if [ -z "$server" ]; then
    server=radar-bundle-ollama
    docker run -d --rm --name "$server" -v radar_ollama:/root/.ollama radar-ollama:local >/dev/null
    trap 'docker stop radar-bundle-ollama >/dev/null 2>&1 || true' EXIT
    for _ in $(seq 1 60); do docker exec "$server" ollama list >/dev/null 2>&1 && break; sleep 1; done
  fi
  for model in "$embedder" "$llm"; do
    docker exec "$server" sh -c "ollama show '$model' >/dev/null 2>&1 || ollama pull '$model'"
  done
  # A model is its manifest and the blobs the manifest names; nothing else
  # Ollama keeps goes into the archive. Read from the server itself, whatever
  # is mounted there.
  docker exec "$server" sh -c '
      set -e
      cd /root/.ollama
      files=""
      for model in "$@"; do
        name=${model%%:*}; tag=${model#*:}; [ "$tag" = "$model" ] && tag=latest
        manifest=models/manifests/registry.ollama.ai/library/$name/$tag
        [ -f "$manifest" ] || { echo "no manifest for $model" >&2; exit 1; }
        files="$files $manifest"
        for digest in $(grep -o "sha256:[0-9a-f]*" "$manifest" | sed "s/:/-/"); do
          files="$files models/blobs/$digest"
        done
      done
      tar -cf - $files
    ' sh "$embedder" "$llm" >"$dir/ollama-models.tar"

  git archive --format=tar -o "$dir/radar-repo.tar" HEAD
  cp "$0" "$dir/offline_bundle.sh"
  (cd "$dir" && sha256sum radar-images.tar ollama-models.tar radar-repo.tar >SHA256SUMS)
  cat >"$dir/bundle.env" <<EOF
RADAR_EMBEDDING_PROVIDER=ollama
RADAR_EMBEDDING_MODEL=$embedder
RADAR_LLM_PROVIDER=ollama
RADAR_LLM_MODEL=$llm
RADAR_LLM_BASE_URL=
EOF
  du -h "$dir"/*.tar
  echo "done: $dir"
}

load() {
  local dir=${1:?usage: offline_bundle.sh load <bundle dir> <install dir>}
  local target=${2:?usage: offline_bundle.sh load <bundle dir> <install dir>}
  (cd "$dir" && sha256sum -c SHA256SUMS) || die "the bundle is damaged"
  mkdir -p "$target/ollama-models"
  tar -xf "$dir/radar-repo.tar" -C "$target"
  echo "loading the images"
  docker load -i "$dir/radar-images.tar"
  echo "unpacking the models"
  tar -xf "$dir/ollama-models.tar" -C "$target/ollama-models"
  {
    cat "$dir/bundle.env"
    echo "OLLAMA_MODELS_DIR=$(abs "$target/ollama-models")"
  } >"$target/.env"
  echo "written $target/.env:"
  cat "$target/.env"
  echo
  echo "start without building, the images are already here:"
  echo "  cd $target && docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile ollama up -d --no-build"
}

case ${1:-} in
  save) shift; save "$@" ;;
  load) shift; load "$@" ;;
  *) die "usage: offline_bundle.sh save <dir> [profile...] | load <bundle dir> <install dir>" ;;
esac
