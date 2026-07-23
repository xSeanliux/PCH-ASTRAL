#!/usr/bin/env bash
# Build weighted TREE-QMC into bin/tree-qmc.
#
# Pinned: upstream main moved to a CMake build (4.x) that embeds R, and the flags
# runWTREEQMC.sh passes (--quartets, --override) exist ONLY in 4.x -- v3 has
# neither. An unpinned clone therefore breaks in both directions, so the commit
# is fixed here. Bump deliberately, and re-run the smoke test afterwards.
set -euo pipefail

QMC_COMMIT="${QMC_COMMIT:-e577f8c}"   # 4.1.5
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/../../.." && pwd)"
SRC="$REPO_ROOT/bin/TREE-QMC"

echo "Installing weighted TREE-QMC ($QMC_COMMIT)"

if [ ! -d "$SRC/.git" ]; then
    git clone --quiet https://github.com/molloy-lab/TREE-QMC "$SRC"
fi
git -C "$SRC" fetch --quiet --all
git -C "$SRC" checkout --quiet "$QMC_COMMIT"

# 4.x embeds R: CMake hard-fails without these three packages.
missing=$(Rscript -e 'cat(paste(setdiff(c("Rcpp","RInside","MSCquartets"),
  rownames(installed.packages())), collapse=" "))' 2>/dev/null || true)
if [ -n "$missing" ]; then
    echo "ERROR: missing R packages: $missing" >&2
    echo "Install them into the first library on R_LIBS, then re-run." >&2
    echo "If that compile dies on 'inaccessible plugin file ... annobin.so', the" >&2
    echo "system R's hardening specs don't match the gcc on PATH; retry with an" >&2
    echo "R_MAKEVARS_USER file setting CFLAGS/CXXFLAGS to plain '-O2 -g -fpic'." >&2
    exit 1
fi

cmake -S "$SRC" -B "$SRC/build" -DCMAKE_BUILD_TYPE=Release >/dev/null
cmake --build "$SRC/build" -j"$(nproc 2>/dev/null || echo 4)" >/dev/null

# bin/tree-qmc is the path runWTREEQMC.sh invokes, matching bin/mb and bin/paup.
cp "$SRC/build/tree-qmc" "$REPO_ROOT/bin/tree-qmc"
echo "weighted TREE-QMC build finished -> bin/tree-qmc"
