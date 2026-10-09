"""RF and network scoring — the only scoring subprocess sites."""

import functools
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from scripts.lib.inference.network_format import convert_contact_network
from scripts.py.cli.schemata import MODEL_GRAPH_REGISTRY


@dataclass
class ScoreResult:
    fn_rate: float
    fp_rate: float


def find_model_graph(
    experiment_folder: Path, horizontal_edges: int, model_tree: int
) -> Path:
    """The model graph file for `(horizontal_edges, model_tree)`; h == 0 is the base tree.

    :raises ValueError: unless the registry has exactly one such graph.
    """
    reg = experiment_folder / "simulation_data" / "model_graph_registry.csv"
    df = pl.read_csv(reg, schema=MODEL_GRAPH_REGISTRY).filter(
        (pl.col("horizontal_edges") == horizontal_edges)
        & (pl.col("model_tree") == model_tree)
    )
    if df.height != 1:
        raise ValueError(
            f"{df.height} model graphs for h={horizontal_edges}, "
            f"model_tree={model_tree} in {reg}; want 1"
        )
    return Path(df["path"][0])


# cache per-run; CSV parsed once per distinct (folder, model_tree). One CLI process = one run, so unbounded is fine.
@functools.lru_cache(maxsize=None)
def resolve_reference_newick(experiment_folder: Path, model_tree: int) -> str:
    """Newick of the BASE TREE (horizontal_edges==0) a network is scored against."""
    return find_model_graph(experiment_folder, 0, model_tree).read_text().strip()


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


# Cached like resolve_reference_newick: one parse per distinct key per process.
@functools.lru_cache(maxsize=None)
def resolve_reference_network(
    experiment_folder: Path, horizontal_edges: int, model_tree: int
) -> str:
    """Rich newick of the reference network; h == 0 is the base tree alone."""
    path = find_model_graph(experiment_folder, horizontal_edges, model_tree)
    return convert_contact_network(path.read_text())


# Relative to the repo root, like RFScorer.R above: the pipeline runs from there.
PHYLONET_JAR = Path("bin/PhyloNet.jar")

# A leaf label follows `(` or `,`; a hybrid reference `#H1` starts with `#`.
_TAXON = re.compile(r"(?<=[(,])[^(),:;#]+")
# `:length` and `:::gamma`; CmpNets rejects inheritance probabilities.
_ANNOTATION = re.compile(r":[^,();]*")
_DISTANCE = re.compile(r"distance between two networks:\s*(\S+)\s+(\S+)\s+(\S+)")


def get_taxa(newick: str) -> set[str]:
    """Return the leaf labels of a Rich newick."""
    return set(_TAXON.findall(newick))


def score_network(estimate_newick: str, reference_newick: str) -> ScoreResult:
    """Score an estimate with `CmpNets -m cluster`, reference as net1.

    The estimate's lengths and inheritance probabilities are stripped first.

    :raises ValueError: if the taxon sets differ.
    :raises RuntimeError: if PhyloNet fails or prints no distance.
    :raises subprocess.TimeoutExpired: past 2 h.
    """
    estimate_newick = _ANNOTATION.sub("", estimate_newick)
    est_taxa, ref_taxa = get_taxa(estimate_newick), get_taxa(reference_newick)
    if est_taxa != ref_taxa:
        # CmpNets returns numbers for mismatched sets; fail loudly instead.
        raise ValueError(f"taxon sets differ: {sorted(est_taxa ^ ref_taxa)}")
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
            ["java", "-jar", str(PHYLONET_JAR), str(tmp)],
            capture_output=True,
            text=True,
            check=False,
            timeout=7200,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"PhyloNet failed (exit {proc.returncode}): {proc.stdout}\n{proc.stderr}"
            )
        m = _DISTANCE.search(proc.stdout)
        if m is None:
            raise RuntimeError(f"PhyloNet: no distance line in {proc.stdout!r}")
        # The third number is their mean; derivable, so not kept.
        fn, fp, _ = (float(x) for x in m.groups())
        return ScoreResult(fn_rate=fn, fp_rate=fp)
    finally:
        tmp.unlink(missing_ok=True)
