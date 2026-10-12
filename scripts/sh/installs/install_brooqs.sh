#!/usr/bin/env bash
# Clone BROOQS (network inference from a tree of blobs) into bin/brooqs-src.
# No build: it is one file, count_quartets.py; numpy and treeswift come from uv.
# bin/brooqs-src, not bin/brooqs: no bin/tree-qmc-vs-bin/TREE-QMC case collision.
# Upstream: github.com/shayesteh99/BROOQS. bin/ is git-ignored; this reproduces it.
set -euo pipefail

BROOQS_COMMIT="${BROOQS_COMMIT:-17b25b2}"   # pinned: the version changes results
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/../../.." && pwd)"
SRC="$REPO_ROOT/bin/brooqs-src"

echo "Installing BROOQS ($BROOQS_COMMIT)"

if [ ! -d "$SRC/.git" ]; then
    git clone --quiet https://github.com/shayesteh99/BROOQS "$SRC"
fi
git -C "$SRC" fetch --quiet --all
git -C "$SRC" checkout --quiet "$BROOQS_COMMIT"
echo "BROOQS $BROOQS_COMMIT installed -> bin/brooqs-src/count_quartets.py"
