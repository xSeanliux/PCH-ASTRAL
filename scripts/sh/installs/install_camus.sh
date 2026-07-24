#!/bin/bash
# Build the CAMUS network-inference binary into bin/camus via Go, then remove the
# source clone (like install_aster.sh). Needs Go on PATH (>= 1.21). Upstream:
# github.com/jsdoublel/camus. bin/ is git-ignored; this reproduces bin/camus.
set -euo pipefail

command -v go >/dev/null || { echo "go not found on PATH; install Go first"; exit 1; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/../../.." && pwd)"
SRC="$REPO_ROOT/bin/camus_src"

echo "Installing CAMUS"

# A prior clone/binary may sit at bin/camus (dir or file); replace it cleanly.
rm -rf "$SRC" "$REPO_ROOT/bin/camus"
git clone --quiet https://github.com/jsdoublel/camus "$SRC"
( cd "$SRC" && go build -o "$REPO_ROOT/bin/camus" )

rm -rf "$SRC"
echo "CAMUS build finished -> bin/camus"
