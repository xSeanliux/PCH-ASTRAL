#!/usr/bin/env bash
#SBATCH --job-name=pch-smoke
#SBATCH --partition=secondary
#SBATCH --account=cs-warnow
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --output=experiments/smoke_slurm/slurm-%j.out
#SBATCH --error=experiments/smoke_slurm/slurm-%j.out

# Run the small-scale MP4/GA/ASTRAL3 smoke test end to end in one job.
# Submit from the repo root:  sbatch experiments/smoke_slurm/run_smoke.sbatch
set -euo pipefail

# SLURM spools a copy of this script, so $0 can't locate the repo; submission
# dir is the repo root (the relative --output paths above assume it too).
REPO="${SLURM_SUBMIT_DIR:-$PWD}"
cd "$REPO"

# conda `phylo` env (java, uv) + pipeline env vars (R_LIBS, PYTHONPATH, scratch).
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate phylo
source scripts/sh/env.sh

YAML=experiments/smoke_slurm/experiment_specification.yaml

echo "=== node: $(hostname)  start: $(date -u +%FT%TZ) ==="
uv run pch simulation          "$YAML"
uv run pch experiment inference "$YAML"
uv run pch experiment score     "$YAML"
uv run pch experiment status    experiments/smoke_slurm
echo "=== done: $(date -u +%FT%TZ) ==="
