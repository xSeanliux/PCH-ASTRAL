"""Consensus-tree summary via scripts/R/consensusTree.R."""

import subprocess
from pathlib import Path


def summarize(trees_path: Path, out_path: Path, *, mode: int, discard: int = 0) -> Path:
    argv = [
        "Rscript",
        "scripts/R/consensusTree.R",
        "-i",
        str(trees_path),
        "-m",
        str(mode),
        "-p",
        "0",
        "-o",
        str(out_path),
    ]
    if discard > 0:
        argv += ["-d", str(discard)]
    proc = subprocess.run(argv, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"consensusTree.R failed (exit {proc.returncode}): {proc.stderr}"
        )
    if not out_path.exists():
        raise RuntimeError(f"consensusTree.R exited 0 but wrote no output: {out_path}")
    return out_path
