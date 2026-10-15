#!/bin/sh
# hadolint over every Dockerfile; the rules and their exceptions are in
# .hadolint.yaml.
#
# CODE_QUALITY_REPORT  a path from the repository root; when set, the findings
#                      also go there for the Code Quality widget of a GitLab
#                      merge request
set -eu
cd "$(dirname "$0")/.."

# shellcheck disable=SC2046 # the paths have no spaces
set -- $(find . \( -name .git -o -name .cache -o -name .venv -o -name node_modules \
  -o -name .gitlab-ci-local \) -prune -o -name Dockerfile -print | sed 's|^\./||' | sort)
if [ -n "${CODE_QUALITY_REPORT:-}" ]; then
  hadolint --format gitlab_codeclimate "$@" >"$CODE_QUALITY_REPORT" || true
fi
hadolint "$@"
