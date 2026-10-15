#!/bin/sh
# Leaked keys and passwords in the history, with gitleaks. Findings that are
# not secrets are listed in .gitleaksignore. Writes gitleaks.xml (JUnit).
#
# COMMIT_RANGE  base..head, the commits of a merge request; empty means the
#               whole history
set -eu
cd "$(dirname "$0")/.."

if [ -n "${COMMIT_RANGE:-}" ]; then
  set -- "--log-opts=$COMMIT_RANGE"
fi
gitleaks git --redact --no-banner --verbose \
  --report-format junit --report-path gitleaks.xml "$@" .
