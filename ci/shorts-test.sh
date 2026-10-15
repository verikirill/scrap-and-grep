#!/bin/sh
# The shorts render service: the TypeScript compiler and the tests of its
# server. Writes shorts/junit.xml.
set -eu
cd "$(dirname "$0")/../shorts"

npm ci --prefer-offline
npx tsc --noEmit
node --test --test-reporter=spec --test-reporter-destination=stdout \
  --test-reporter=junit --test-reporter-destination=junit.xml "server/**/*.test.ts"
