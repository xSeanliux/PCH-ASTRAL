#!/usr/bin/env bash
# Install a pinned Julia to bin/julia and SNaQ.jl into bin/julia-depot, from the
# committed scripts/jl/{Project,Manifest}.toml. bin/ is git-ignored; this reproduces it.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/../../.." && pwd)"
JULIA_VERSION="${JULIA_VERSION:-1.12.7}"
MINOR="${JULIA_VERSION%.*}"

case "$(uname -s)-$(uname -m)" in
    Darwin-arm64) URL="mac/aarch64/$MINOR/julia-$JULIA_VERSION-macaarch64.tar.gz" ;;
    Darwin-x86_64) URL="mac/x64/$MINOR/julia-$JULIA_VERSION-mac64.tar.gz" ;;
    Linux-x86_64) URL="linux/x64/$MINOR/julia-$JULIA_VERSION-linux-x86_64.tar.gz" ;;
    Linux-aarch64) URL="linux/aarch64/$MINOR/julia-$JULIA_VERSION-linux-aarch64.tar.gz" ;;
    *) echo "unsupported platform: $(uname -s)-$(uname -m)"; exit 1 ;;
esac

echo "Installing Julia $JULIA_VERSION"
mkdir -p "$REPO_ROOT/bin"
curl -fsSL "https://julialang-s3.julialang.org/bin/$URL" | tar -xz -C "$REPO_ROOT/bin"
ln -sfn "julia-$JULIA_VERSION/bin/julia" "$REPO_ROOT/bin/julia"

# The depot lives in bin/, not ~/.julia (home is quota-limited on the cluster).
echo "Installing SNaQ.jl (scripts/jl/Manifest.toml) and precompiling"
JULIA_DEPOT_PATH="$REPO_ROOT/bin/julia-depot" "$REPO_ROOT/bin/julia" \
    --project="$REPO_ROOT/scripts/jl" -e 'using Pkg; Pkg.instantiate(); Pkg.precompile()'
echo "Julia $JULIA_VERSION + SNaQ.jl installed -> bin/julia, bin/julia-depot"
