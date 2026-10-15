#!/bin/sh
# Rolls the stand out with docker compose: the compose file and configs of
# this commit and the images the pipeline pushed to the project registry.
# The stand keeps its own .env with its secrets; only the image and profile
# lines of it are written here, so that a `docker compose` typed on the stand
# later runs the same stack.
#
# STAND_DEPLOY says how the stand is reached:
#   ssh    STAND_SSH_HOST, STAND_SSH_USER, STAND_SSH_PORT (22) and two File
#          variables, STAND_SSH_KEY (a private key) and STAND_SSH_KNOWN_HOSTS
#   local  the runner itself runs on the stand: the Docker socket and STAND_DIR
#          are mounted into the job at the same paths
#
# STAND_DIR (/opt/scrapgrep) holds the stack. STAND_PROFILES lists the compose
# profiles besides the core, comma-separated (video, mail, s3); voice and
# docling are refused, the stand runs without them.
set -eu

: "${RADAR_IMAGE_PREFIX:?}" "${RADAR_IMAGE_TAG:?}"
: "${CI_REGISTRY:?}" "${CI_REGISTRY_USER:?}" "${CI_REGISTRY_PASSWORD:?}"
dir=${STAND_DIR:-/opt/scrapgrep}
profiles=$(printf '%s' "${STAND_PROFILES:-}" | tr -d ' ')

case ",$profiles," in
  *,voice,* | *,docling,*)
    echo "STAND_PROFILES=$profiles: the stand runs without voice and docling" >&2
    exit 1
    ;;
esac

case ${STAND_DEPLOY:-} in
  ssh)
    : "${STAND_SSH_HOST:?}" "${STAND_SSH_USER:?}"
    : "${STAND_SSH_KEY:?}" "${STAND_SSH_KNOWN_HOSTS:?}"
    # ssh refuses a key that others may read.
    chmod 600 "$STAND_SSH_KEY"
    on_stand() {
      ssh -i "$STAND_SSH_KEY" -p "${STAND_SSH_PORT:-22}" \
        -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes \
        -o UserKnownHostsFile="$STAND_SSH_KNOWN_HOSTS" \
        "$STAND_SSH_USER@$STAND_SSH_HOST" "$1"
    }
    ;;
  local)
    on_stand() { sh -c "$1"; }
    ;;
  *)
    echo "STAND_DEPLOY is ssh or local, not '${STAND_DEPLOY:-}'" >&2
    exit 1
    ;;
esac

echo "stand: $dir ($STAND_DEPLOY), images ${RADAR_IMAGE_PREFIX}*:$RADAR_IMAGE_TAG," \
  "profiles: ${profiles:-core only}"
on_stand "docker compose version"

# What compose reads besides the images: the configs and the sample of
# articles the first start loads.
tar -cf - docker-compose.yml clickhouse data/samples |
  on_stand "mkdir -p '$dir' && tar -xf - -C '$dir'"

on_stand "cd '$dir' && { [ -s .env ] || echo 'no .env on the stand: the defaults are used'; } \
  && touch .env \
  && sed -i -e '/^RADAR_IMAGE_PREFIX=/d' -e '/^RADAR_IMAGE_TAG=/d' -e '/^COMPOSE_PROFILES=/d' .env \
  && printf '%s\n' 'RADAR_IMAGE_PREFIX=$RADAR_IMAGE_PREFIX' 'RADAR_IMAGE_TAG=$RADAR_IMAGE_TAG' \
     'COMPOSE_PROFILES=$profiles' >> .env"

# The job token signs in for the pull and expires with the job; the stand
# keeps no registry password after it.
printf '%s' "$CI_REGISTRY_PASSWORD" | on_stand "docker login --username '$CI_REGISTRY_USER' \
  --password-stdin '$CI_REGISTRY' >/dev/null \
  && cd '$dir' && { docker compose pull --quiet; pulled=\$?; \
  docker logout '$CI_REGISTRY' >/dev/null; exit \$pulled; }"

# Compose waits for the migrations to finish and for every service with a
# healthcheck to report healthy.
on_stand "cd '$dir' && docker compose up --detach --no-build --remove-orphans \
  --wait --wait-timeout 900"

# A profile taken out of STAND_PROFILES leaves its containers running:
# --remove-orphans keeps every service the compose file still names.
on_stand "cd '$dir' && sh -s" <<'EOF'
active=" $(docker compose config --services | tr '\n' ' ') "
for service in $(docker compose --profile '*' config --services); do
  case $active in
    *" $service "*) ;;
    *) docker compose --profile '*' rm --stop --force "$service" ;;
  esac
done
EOF

on_stand "cd '$dir' && docker compose ps --format 'table {{.Service}}\t{{.Image}}\t{{.Status}}'"
