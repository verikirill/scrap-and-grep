#!/bin/sh
# One test run as a Markdown table for the summary of a GitHub Actions job:
# tests, failures, skips and line coverage.
#
#   sh ci/test-summary.sh <title> <JUnit XML> [<Cobertura XML>]
#
# Appends to GITHUB_STEP_SUMMARY, or prints when it is not set.
set -eu
title=$1 junit=$2 cobertura=${3:-}
out=${GITHUB_STEP_SUMMARY:-/dev/stdout}

count() { grep -o "<$1[ />]" "$junit" | wc -l | tr -d ' '; }
attribute() {
  grep -o '<coverage [^>]*' "$cobertura" | grep -o " $1=\"[0-9.]*\"" | head -n 1 | tr -dc '0-9.'
}

if [ ! -f "$junit" ]; then
  printf '### %s\n\nThe job ended before the tests wrote %s.\n' "$title" "$junit" >>"$out"
  exit 0
fi
coverage=-
if [ -n "$cobertura" ] && [ -f "$cobertura" ]; then
  coverage=$(awk -v covered="$(attribute lines-covered)" -v valid="$(attribute lines-valid)" \
    'BEGIN { printf "%.1f%% (%d of %d lines)", valid ? 100 * covered / valid : 0, covered, valid }')
fi
cat >>"$out" <<EOF
### $title

| Tests | Failed | Skipped | Line coverage |
|---|---|---|---|
| $(count testcase) | $(($(count failure) + $(count error))) | $(count skipped) | $coverage |
EOF
