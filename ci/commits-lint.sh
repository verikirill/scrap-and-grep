#!/bin/sh
# Every commit of a merge request follows the convention of the history,
# "type(scope): what changed". Merge commits keep the message GitLab gives
# them and are skipped.
#
# COMMIT_RANGE  base..head, by default the commits of the current branch that
#               origin/main lacks
set -eu
cd "$(dirname "$0")/.."

range=${COMMIT_RANGE:-origin/main..HEAD}
types='feat|fix|docs|refactor|test|perf|ci|build|chore|style|revert'
log=$(git log --no-merges --format='%h %s' "$range")
bad=$(printf '%s\n' "$log" | grep -vE "^([0-9a-f]+ ($types)(\([a-z0-9/_.-]+\))?!?: .+)?$" || true)
if [ -n "$bad" ]; then
  echo "These commits do not follow 'type(scope): what changed':" >&2
  echo "$bad" >&2
  exit 1
fi
echo "$(printf '%s\n' "$log" | grep -c .) commits of $range follow 'type(scope): what changed'"
