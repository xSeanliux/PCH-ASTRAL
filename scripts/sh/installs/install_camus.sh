#!/bin/bash
# Install the CAMUS network-inference binary to bin/camus. Needs Go on PATH.
# Upstream: github.com/jsdoublel/camus. bin/ is git-ignored; this reproduces it.
set -euo pipefail

# Pinned: the version changes results. v1.0.2 fixes edge scoring and ordering,
# which affect networks with two or more added edges.
CAMUS_VERSION="${CAMUS_VERSION:-v1.0.2}"

command -v go >/dev/null || { echo "go not found on PATH; install Go first"; exit 1; }

echo "Installing CAMUS $CAMUS_VERSION"
rm -rf bin/camus  # a prior manual `git clone` may have left a directory here
GOBIN="$PWD/bin" go install "github.com/jsdoublel/camus@$CAMUS_VERSION"
echo "CAMUS $CAMUS_VERSION installed -> bin/camus"
