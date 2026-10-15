#!/bin/sh
# Known vulnerabilities in the locked dependencies, with osv-scanner. The
# parts of the stand decide the result; the advisories of tts and docparser,
# which follow the PyTorch releases, are printed for information.
set -eu
cd "$(dirname "$0")/.."

# The scanner's image keeps the binary at the root of its file system.
osv_scanner=$(command -v osv-scanner || echo /osv-scanner)
"$osv_scanner" scan source --lockfile backend/uv.lock --lockfile browser/uv.lock \
  --lockfile frontend/package-lock.json --lockfile shorts/package-lock.json
"$osv_scanner" scan source --lockfile tts/uv.lock --lockfile docparser/uv.lock ||
  echo "tts and docparser: the advisories above are for information"
