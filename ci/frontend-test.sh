#!/bin/sh
# The tests of the web app with coverage of every source file, the settings of
# vite.config.ts. Writes frontend/junit.xml and
# frontend/coverage/cobertura-coverage.xml.
set -eu
cd "$(dirname "$0")/../frontend"

npm ci --prefer-offline
# Plain text, so that GitLab reads the coverage line from the log.
NO_COLOR=1 npx vitest run --coverage \
  --reporter=default --reporter=junit --outputFile.junit=junit.xml
