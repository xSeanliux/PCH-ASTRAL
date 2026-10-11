"""RF and network scoring — the only scoring subprocess sites."""

import functools
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from scripts.lib.inference.network_format import convert_contact_network
from scripts.lib.model.model_graph import find_model_graph


@dataclass
class ScoreResult:
    fn_rate: float
    fp_rate: float


# cache per-run; CSV parsed once per distinct (folder, model_tree). One CLI process = one run, so unbounded is fine.
@functools.lru_cache(maxsize=None)
def resolve_reference_newick(experiment_folder: Path, model_tree: int) -> str:
    """Newick of the base tree (h = 0) a network is scored against.

    :param experiment_folder: experiment root, holding `simulation_data/`.
    :param model_tree: base tree index.
    :returns: the base tree's newick, stripped.
    :raises ValueError: if the base tree is not registered exactly once.
    """
    return find_model_graph(experiment_folder, 0, model_tree).path.read_text().strip()


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
    """Rich newick of the reference network; h = 0 is the base tree alone.

    :param experiment_folder: experiment root, holding `simulation_data/`.
    :param horizontal_edges: reticulation count.
    :param model_tree: base tree index.
    :returns: the network as rich newick.
    :raises ValueError: if the graph is not registered exactly once.
    """
    graph = find_model_graph(experiment_folder, horizontal_edges, model_tree)
    return convert_contact_network(graph.path.read_text())


# Relative to the repo root, like RFScorer.R above: the pipeline runs from there.
PHYLONET_JAR = Path("bin/PhyloNet.jar")

# A leaf label follows `(` or `,`; a hybrid reference `#H1` starts with `#`.
_TAXON = re.compile(r"(?<=[(,])[^(),:;#]+")
_DISTANCE = re.compile(r"distance between two networks:\s*(\S+)\s+(\S+)\s+(\S+)")


def get_taxa(newick: str) -> set[str]:
    """Return the leaf labels of a Rich newick."""
    return set(_TAXON.findall(newick))


def score_network(estimate_newick: str, reference_newick: str) -> ScoreResult:
    """Score an estimate with `CmpNets -m cluster`, reference as net1.

    :raises ValueError: if the taxon sets differ.
    :raises RuntimeError: if PhyloNet fails or prints no distance.
    :raises subprocess.TimeoutExpired: past 2 h.
    """
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
