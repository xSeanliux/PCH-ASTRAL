#!/bin/bash
# Install the CAMUS network-inference binary to bin/camus. Needs Go and git on PATH.
# Source: our fork github.com/xSeanliux/camus (adds -B, bidirectional). Its go.mod
# keeps module github.com/jsdoublel/camus, so `go install` by fork path fails: build.
# bin/ is git-ignored; this reproduces it.
set -euo pipefail

# Pinned: the version changes results. Override with a fork ref or SHA (no tags).
CAMUS_VERSION="${CAMUS_VERSION:-e454cb3193d605f82ae96729b923520b7527fe61}"

command -v go >/dev/null || { echo "go not found on PATH; install Go first"; exit 1; }

echo "Installing CAMUS $CAMUS_VERSION"
src="$(mktemp -d)"
trap 'rm -rf "$src"' EXIT
git clone -q https://github.com/xSeanliux/camus "$src"
git -C "$src" checkout -q "$CAMUS_VERSION"
mkdir -p bin && rm -rf bin/camus  # a prior manual `git clone` may have left a directory here
(cd "$src" && go build -o "$OLDPWD/bin/camus" .)
echo "CAMUS $CAMUS_VERSION installed -> bin/camus"
