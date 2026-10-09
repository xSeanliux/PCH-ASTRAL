import shutil
from pathlib import Path

import polars as pl
import pytest

from scripts.lib.inference.scoring import (
    PHYLONET_JAR,
    find_model_graph,
    score_network,
    resolve_reference_network,
    score,
    get_taxa,
)

needs_r = pytest.mark.skipif(
    shutil.which("Rscript") is None, reason="Rscript not installed"
)
needs_phylonet = pytest.mark.skipif(
    shutil.which("java") is None or not PHYLONET_JAR.exists(),
    reason="java or bin/PhyloNet.jar missing",
)

TREE = "((t1,t2),(t3,t4),t5);"


@needs_r
def test_identical_trees_zero_rates() -> None:
    r = score(TREE, TREE)
    assert r.fn_rate == 0.0
    assert r.fp_rate == 0.0


@needs_r
def test_discordant_estimate_has_fn() -> None:
    estimate = "((t1,t3),(t2,t4),t5);"
    r = score(estimate, TREE)
    assert r.fn_rate > 0


REF = "((((A,((B)#H2,#H1)),((C)#H1,#H2)),(D,E)),OUT);"


def test_taxa_skips_hybrid_labels_and_lengths():
    assert get_taxa("((A:1,(B:1)#H1:1),(#H1,C:1));") == {"A", "B", "C"}


def test_score_network_rejects_mismatched_taxa():
    with pytest.raises(ValueError, match="taxon sets differ"):
        score_network("((A,B),C);", REF)


def test_resolve_reference_network_reads_the_registered_file(tmp_path: Path):
    net = tmp_path / "net1-1.txt"
    net.write_text("((((A:1,B:1):1,C:1):1,(D:1,E:1):1):1,OUT:1)\nB;C;0.5;0.3\n")
    (tmp_path / "simulation_data").mkdir()
    pl.DataFrame(
        {
            "horizontal_edges": [1],
            "model_tree": [1],
            "path": [str(net)],
            "outgroup_label": ["OUT"],
            "outgroup_seed": [1],
            "outgroup_branch_length": [1.0],
            "ingroup_stem_length": [1.0],
        }
    ).write_csv(tmp_path / "simulation_data" / "model_graph_registry.csv")
    assert resolve_reference_network(tmp_path, 1, 1) == REF
    with pytest.raises(ValueError, match="0 model graphs"):
        resolve_reference_network(tmp_path, 2, 1)


def test_find_model_graph_rejects_duplicates(tmp_path: Path):
    (tmp_path / "simulation_data").mkdir()
    pl.DataFrame(
        {
            "horizontal_edges": [1, 1],
            "model_tree": [1, 1],
            "path": ["a", "b"],
            "outgroup_label": ["OUT"] * 2,
            "outgroup_seed": [1] * 2,
            "outgroup_branch_length": [1.0] * 2,
            "ingroup_stem_length": [1.0] * 2,
        }
    ).write_csv(tmp_path / "simulation_data" / "model_graph_registry.csv")
    with pytest.raises(ValueError, match="2 model graphs"):
        find_model_graph(tmp_path, 1, 1)


@needs_phylonet
def test_score_network_reference_against_itself_is_zero():
    s = score_network(REF, REF)
    assert (s.fn_rate, s.fp_rate) == (0.0, 0.0)


@needs_phylonet
def test_score_network_plain_tree_has_fn():
    # scoring.md: the plain tree scores FN 0.333, FP 0.
    s = score_network("((((A,B),C),(D,E)),OUT);", REF)
    assert s.fn_rate == pytest.approx(1 / 3)
    assert s.fp_rate == 0.0


@needs_phylonet
def test_score_network_strips_estimate_annotations():
    s = score_network("((((A:1,B:2):0.5,C),(D,E)),OUT:3);", REF)
    assert s.fn_rate == pytest.approx(1 / 3)
