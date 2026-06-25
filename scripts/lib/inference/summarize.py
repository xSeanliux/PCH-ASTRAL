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
    subprocess.run(argv, check=True)
    return out_path
