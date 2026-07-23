#!/usr/bin/env bash
# Build ASTER (wastral + astral4) from source into bin/.
#
# Prebuilt release binaries are compiled against a newer macOS than some hosts
# run, so they die at load with "built for macOS 15.0 which is newer than
# running OS". Building here links against the local toolchain instead.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/../../.." && pwd)"
SRC="$REPO_ROOT/bin/ASTER"

echo "Installing ASTER (build from source)"

if [ ! -d "$SRC/.git" ]; then
    git clone --quiet https://github.com/chaoszhang/ASTER "$SRC"
fi

# wastral -> src/astral-hybrid.cpp, astral (->bin/astral4) -> src/astral.cpp
# (ASTER makefile targets; -march=native -Ofast, -std=c++17 -O2 fallback built in).
make -C "$SRC" wastral
make -C "$SRC" astral

# bin/wastral and bin/astral4 are the paths runWASTRAL.sh and the runners expect.
cp "$SRC/bin/wastral" "$REPO_ROOT/bin/wastral"
cp "$SRC/bin/astral4" "$REPO_ROOT/bin/astral4"
echo "ASTER build finished -> bin/wastral, bin/astral4"
