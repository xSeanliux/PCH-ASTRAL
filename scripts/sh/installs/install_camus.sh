#!/bin/bash
# Install the CAMUS network-inference binary to bin/camus. Needs Go on PATH.
# Upstream: github.com/jsdoublel/camus. bin/ is git-ignored; this reproduces it.
set -euo pipefail

command -v go >/dev/null || { echo "go not found on PATH; install Go first"; exit 1; }

echo "Installing CAMUS"
rm -rf bin/camus  # a prior manual `git clone` may have left a directory here
GOBIN="$PWD/bin" go install github.com/jsdoublel/camus@latest
echo "CAMUS installed -> bin/camus"
