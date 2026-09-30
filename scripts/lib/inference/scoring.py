"""RF and network scoring — the only scoring subprocess sites."""

import functools
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from scripts.lib.inference.network_format import contact_network_to_rich_newick
from scripts.py.cli.schemata import MODEL_GRAPH_REGISTRY


@dataclass
class ScoreResult:
    fn_rate: float
    fp_rate: float


# cache per-run; CSV parsed once per distinct (folder, model_tree). One CLI process = one run, so unbounded is fine.
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


@dataclass
class NetworkScore:
    fn: float
    fp: float
    avg: float


# Cached like resolve_reference_newick: one parse per distinct key per process.
@functools.lru_cache(maxsize=None)
def resolve_reference_network(
    experiment_folder: Path, horizontal_edges: int, model_tree: int
) -> str:
    """Rich newick of the reference network; h == 0 is the base tree alone."""
    reg = experiment_folder / "simulation_data" / "model_graph_registry.csv"
    df = pl.read_csv(reg, schema=MODEL_GRAPH_REGISTRY).filter(
        (pl.col("horizontal_edges") == horizontal_edges)
        & (pl.col("model_tree") == model_tree)
    )
    if df.height == 0:
        raise ValueError(
            f"No network for h={horizontal_edges}, model_tree={model_tree} in {reg}"
        )
    return contact_network_to_rich_newick(
        Path(df.row(0, named=True)["path"]).read_text()
    )


# A leaf label follows `(` or `,`; a hybrid reference `#H1` starts with `#`.
_TAXON = re.compile(r"(?<=[(,])[^(),:;#]+")
_DISTANCE = re.compile(r"distance between two networks:\s*(\S+)\s+(\S+)\s+(\S+)")


def taxa(newick: str) -> set[str]:
    return set(_TAXON.findall(newick))


def network_score(
    estimate_newick: str, reference_newick: str, *, timeout_seconds: float = 7200
) -> NetworkScore:
    """`CmpNets -m cluster`, reference as net1. Raises subprocess.TimeoutExpired
    past `timeout_seconds`."""
    if taxa(estimate_newick) != taxa(reference_newick):
        # CmpNets returns numbers for mismatched sets; fail loudly instead.
        raise ValueError(
            f"taxon sets differ: {sorted(taxa(estimate_newick) ^ taxa(reference_newick))}"
        )
    nexus = (
        "#NEXUS\nBEGIN NETWORKS;\n"
        f"Network net1 = {reference_newick.strip().rstrip(';')};\n"
        f"Network net2 = {estimate_newick.strip().rstrip(';')};\n"
        "END;\nBEGIN PHYLONET;\nCmpNets net1 net2 -m cluster;\nEND;\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nex", delete=False) as f:
        f.write(nexus)
        tmp = Path(f.name)
    try:
        proc = subprocess.run(
            ["java", "-jar", "bin/PhyloNet.jar", str(tmp)],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"PhyloNet failed (exit {proc.returncode}): {proc.stdout}{proc.stderr}"
            )
        m = _DISTANCE.search(proc.stdout)
        if m is None:
            raise RuntimeError(f"PhyloNet: no distance line in {proc.stdout!r}")
        fn, fp, avg = (float(x) for x in m.groups())
        return NetworkScore(fn=fn, fp=fp, avg=avg)
    finally:
        tmp.unlink(missing_ok=True)
