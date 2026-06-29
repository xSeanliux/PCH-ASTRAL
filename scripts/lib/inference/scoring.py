"""RF scoring via scripts/R/RFScorer.R — the only scoring subprocess site."""

import functools
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from scripts.py.cli.schemata import MODEL_GRAPH_REGISTRY


@dataclass
class ScoreResult:
    fn_rate: float
    fp_rate: float


# ponytail: cache per-run; CSV parsed once per distinct (folder, model_tree). One CLI process = one run, so unbounded is fine.
@functools.lru_cache(maxsize=None)
def resolve_reference_newick(experiment_folder: Path, model_tree: int) -> str:
    """Newick of the BASE TREE (horizontal_edges==0) a network is scored against."""
    reg = experiment_folder / "simulation_data" / "model_graph_registry.csv"
    df = pl.read_csv(reg, schema=MODEL_GRAPH_REGISTRY).filter(
        (pl.col("horizontal_edges") == 0) & (pl.col("model_tree") == model_tree)
    )
    if df.height == 0:
        raise ValueError(f"No base tree for model_tree={model_tree} in {reg}")
    return Path(df.row(0, named=True)["path"]).read_text().strip()


def score(
    estimate_newick: str,
    reference_newick: str,
) -> ScoreResult:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".tree", delete=False) as f:
        f.write(estimate_newick)
        tmp = Path(f.name)
    try:
        argv = [
            "Rscript",
            "scripts/R/RFScorer.R",
            "-i",
            str(tmp),
            "-f",
            "newick",
            "-r",
            reference_newick,
            "-m",
            "1",
            "-p",
            "0",
        ]
        proc = subprocess.run(argv, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(
                f"RFScorer.R failed (exit {proc.returncode}): {proc.stderr}"
            )
        parts = proc.stdout.split()
        if len(parts) != 2:
            raise RuntimeError(f"RFScorer.R: expected 'fn fp', got {proc.stdout!r}")
        fn, fp = parts
        return ScoreResult(fn_rate=float(fn), fp_rate=float(fp))
    finally:
        tmp.unlink(missing_ok=True)
