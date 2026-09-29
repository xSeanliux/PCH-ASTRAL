from io import StringIO
from pathlib import Path

import polars as pl
import pytest
from Bio import Phylo

from scripts.lib.experiment import CamusConfig
from scripts.lib.inference.runners import ASTRAL3Runner
from scripts.py.guide_tree import (
    experiment_of,
    guide_newick,
    model_tree_of,
    rooted_topology,
)

G = CamusConfig.GuideTree

BASE_TREE = "(((t1:0.1,t2:0.1):0.2,(t3:0.1,t4:0.1):0.2):0.05,OUT:0.95);"
# As ASTRAL writes it: unrooted, with support values and lengths.
ESTIMATE = "((t1,t2)0.9:1.2,(t3,OUT)0.7:0.4,t4);"


def _experiment(tmp_path: Path, outgroup: str | None = "OUT") -> tuple[Path, Path]:
    """An experiment with one dataset on model tree 1; returns (dataset, output_dir)."""
    sim = tmp_path / "simulation_data"
    condition = sim / "simulated_data" / "high_0.1_4_80"
    condition.mkdir(parents=True)
    dataset = condition / "sim_1_1_1.csv"
    dataset.write_text("id,feature,weight,OUT,t1,t2,t3,t4\n")
    base_tree = sim / "model_tree_1.txt"
    base_tree.write_text(BASE_TREE + "\n")

    pl.DataFrame(
        {
            "poly_level": ["high"],
            "character_count": [80],
            "min_tree_height": [4],
            "homoplasy_factor": [0.1],
            "horizontal_edges": [1],
            "model_tree": [1],
            "replica": [1],
            "path": [str(dataset)],
        }
    ).write_csv(sim / "simulated_data_registry.csv")
    pl.DataFrame(
        {
            "horizontal_edges": [0],
            "model_tree": [1],
            "path": [str(base_tree)],
            "outgroup": [outgroup],
        },
        schema_overrides={"outgroup": pl.String},
    ).write_csv(sim / "model_graph_registry.csv")
    return dataset, tmp_path / "inference_data" / "high_0.1_4_80"


def _root_children(newick: str) -> list[set[str]]:
    tree = Phylo.read(StringIO(newick), "newick")
    return [{t.name for t in c.get_terminals()} for c in tree.root.clades]


def test_rooting_puts_the_outgroup_beside_everything_else():
    rooted = rooted_topology(ESTIMATE, "OUT")
    assert sorted(_root_children(rooted), key=len) == [
        {"OUT"},
        {"t1", "t2", "t3", "t4"},
    ]


def test_rooting_drops_lengths_and_support():
    assert rooted_topology(BASE_TREE, "OUT") == "(((t1,t2),(t3,t4)),OUT);"


def test_rooting_a_rooted_tree_changes_nothing():
    once = rooted_topology(ESTIMATE, "OUT")
    assert rooted_topology(once, "OUT") == once


def test_without_an_outgroup_the_root_stays_where_it_was():
    assert (
        rooted_topology("((t1:1,t2:1):1,(t3:1,t4:1):1);", None) == "((t1,t2),(t3,t4));"
    )


def test_polytomies_are_kept():
    rooted = rooted_topology("((t1,t2,t3),(t4,OUT));", "OUT")
    tree = Phylo.read(StringIO(rooted), "newick")
    assert any(len(c.clades) == 3 for c in tree.get_nonterminals())


def test_an_absent_outgroup_is_an_error():
    with pytest.raises(ValueError, match="not in the tree"):
        rooted_topology("((t1,t2),(t3,t4));", "OUT")


def test_a_dataset_finds_its_experiment_and_model_tree(tmp_path: Path):
    dataset, _ = _experiment(tmp_path)
    assert experiment_of(dataset) == tmp_path.resolve()
    assert model_tree_of(tmp_path, dataset) == 1


def test_a_dataset_outside_an_experiment_is_an_error(tmp_path: Path):
    with pytest.raises(ValueError, match="not inside an experiment"):
        experiment_of(tmp_path / "loose.csv")


def test_true_tree_is_the_base_tree(tmp_path: Path):
    dataset, output_dir = _experiment(tmp_path)
    assert guide_newick(G.TRUE_TREE, dataset, output_dir) == "(((t1,t2),(t3,t4)),OUT);"


def test_a_method_guide_is_that_methods_estimate_rooted(tmp_path: Path):
    dataset, output_dir = _experiment(tmp_path)
    estimate = ASTRAL3Runner.point_estimate_path(output_dir, dataset.stem)
    estimate.parent.mkdir(parents=True)
    estimate.write_text(ESTIMATE + "\n")

    guide = guide_newick(G.ASTRAL3, dataset, output_dir)
    assert sorted(_root_children(guide), key=len) == [
        {"OUT"},
        {"t1", "t2", "t3", "t4"},
    ]
