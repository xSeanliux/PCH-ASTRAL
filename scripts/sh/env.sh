#!/usr/bin/env bash
# Environment for the config-driven `pch` pipeline. Source before running it,
# interactively or from a SLURM job:
#   source scripts/sh/env.sh
# Idempotent and portable: every machine path is derived from this file's own
# location, so there are no hardcoded cluster paths.

# Repo root = two levels up from scripts/sh/env.sh.
_PCH_REPO="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/../.." && pwd)"

# R library for nexus-gen/scoring/consensus (built alongside the repo). Put it
# first; without these packages commandLineNex.R halts and MP4/GA silently emit
# no tree. Any pre-existing R_LIBS is kept as a fallback.
# Rlibs-4.6: rebuilt under the cluster's R 4.6.1 (the 4.4.2-built ../Rlibs break
# on 4.6 with `rlang: undefined symbol SETLENGTH`). Rebuild deps into a matching
# ../Rlibs-<major.minor> if the system R is upgraded again.
export R_LIBS="$(dirname "$_PCH_REPO")/Rlibs-4.6${R_LIBS:+:$R_LIBS}"

# Beat the `OneMostProb` shadow: another project on PYTHONPATH ships its own
# top-level `scripts/` package. Prepending this repo makes `import scripts`
# resolve here, fixing `ModuleNotFoundError: scripts.py.cli` under `uv run pch`.
export PYTHONPATH="${_PCH_REPO}${PYTHONPATH:+:$PYTHONPATH}"

# ASTRAL JVM heap. 320 chars (~410k weighted quartets) OOMs the 8g default and
# 640 needs far more, so run the sweep with a large heap.
export PCH_ASTRAL_XMX="${PCH_ASTRAL_XMX:-256g}"

# Short scratch path — MrBayes caps input filenames at 99 chars.
export PCH_SCRATCH="${PCH_SCRATCH:-$HOME/scratch}"
mkdir -p "$PCH_SCRATCH"

unset _PCH_REPO
