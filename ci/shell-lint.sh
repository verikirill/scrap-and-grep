#!/bin/sh
# Every shell script of the repository, checked by shellcheck.
set -eu
cd "$(dirname "$0")/.."

# shellcheck disable=SC2046 # the paths have no spaces
set -- $(find . \( -name .git -o -name .cache -o -name .venv -o -name node_modules \
  -o -name .gitlab-ci-local \) -prune -o -name '*.sh' -print | sed 's|^\./||' | sort)
echo "shellcheck: $*"
shellcheck "$@"
