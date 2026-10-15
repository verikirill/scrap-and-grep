#!/bin/sh
# The web app: oxlint, the oxfmt formatter and the TypeScript compiler.
#
# CODE_QUALITY_REPORT  a path from the repository root; when set, the oxlint
#                      findings also go there for the Code Quality widget of
#                      a GitLab merge request
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
cd "$root/frontend"

npm ci --prefer-offline
if [ -n "${CODE_QUALITY_REPORT:-}" ]; then
  # oxlint writes the paths from the repository root, as the widget wants.
  npx oxlint --format=gitlab >"$root/$CODE_QUALITY_REPORT" || true
fi
npx oxlint
npx oxfmt --check src vite.config.ts
npx tsc -b
