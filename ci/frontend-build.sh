#!/bin/sh
# The production build of the web app, into frontend/dist.
set -eu
cd "$(dirname "$0")/../frontend"

npm ci --prefer-offline
npx vite build
