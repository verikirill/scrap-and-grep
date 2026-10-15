#!/bin/sh
# Builds the images of the stand with the Docker at hand: backend (the api
# service), web, browser, shorts and the egress proxy of the airgap override,
# or the services named as arguments. Their names come from RADAR_IMAGE_PREFIX
# and RADAR_IMAGE_TAG, as in docker-compose.yml.
#
# PUSH_IMAGES  true pushes them to REGISTRY, signed in as REGISTRY_USER with
#              REGISTRY_PASSWORD
# IMAGE_ALIAS  a second tag for the pushed images, such as main or the name of
#              a release tag
set -eu
cd "$(dirname "$0")/.."

[ $# -gt 0 ] || set -- api web browser shorts egress
compose() {
  docker compose -f docker-compose.yml -f docker-compose.airgap.yml --profile video "$@"
}
push=${PUSH_IMAGES:-false}
if [ "$push" = true ]; then
  : "${REGISTRY:?}" "${REGISTRY_USER:?}" "${REGISTRY_PASSWORD:?}" "${RADAR_IMAGE_PREFIX:?}"
fi

docker version --format 'Docker {{.Server.Version}}'
compose build --pull "$@"
if [ "$push" != true ]; then
  exit 0
fi

printf '%s' "$REGISTRY_PASSWORD" |
  docker login --username "$REGISTRY_USER" --password-stdin "$REGISTRY"
compose push --quiet "$@"
if [ -n "${IMAGE_ALIAS:-}" ]; then
  # A slash is not allowed in an image tag.
  moving=$(printf '%s' "$IMAGE_ALIAS" | tr -c 'A-Za-z0-9_.-' '-')
  for image in $(compose config --images "$@" | sort -u); do
    case $image in "$RADAR_IMAGE_PREFIX"*) ;; *) continue ;; esac
    docker tag "$image" "${image%:*}:$moving"
    docker push --quiet "${image%:*}:$moving"
  done
fi
docker logout "$REGISTRY"
