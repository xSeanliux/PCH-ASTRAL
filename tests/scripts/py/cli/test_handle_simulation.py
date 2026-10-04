from pathlib import Path

import polars as pl
import pytest

from scripts.lib.experiment import ExperimentSimulationConfig
from scripts.py.cli.handle_simulation import copy_model_graphs
from scripts.py.cli.schemata import MODEL_GRAPH_REGISTRY

TREES = [
    "((t1:0.1,t2:0.2):0.3,(t3:0.1,t4:0.2):0.3);",
    "((t1:0.2,t3:0.2):0.3,(t2:0.1,t4:0.2):0.3);",
]
# Network line 1 has no terminator; the last line has no newline.
NETWORK = "((t1:0.1,t2:0.2):0.3,(t3:0.1,t4:0.2):0.3)\nt1;(t3:0.1,t4:0.2);0.35;0.19"


def _config(
    tmp_path: Path, horizontal_edges: list[int], outgroup_label: str | None
) -> ExperimentSimulationConfig:
    trees = tmp_path / "trees.txt"
    trees.write_text("\n".join(TREES) + "\n")
    networks = tmp_path / "nets"
    networks.mkdir()
    for i in (1, 2):
        (networks / f"net1-{i}.txt").write_text(NETWORK)
    return ExperimentSimulationConfig(
        n_horizontal_edges=horizontal_edges,
        n_trees=2,
        n_replicas=1,
        n_taxa=4,
        outgroup_label=outgroup_label,
        base_config_dir=tmp_path / "configs",
        base_trees_file=trees,
        base_networks_dir=networks,
        simulation_params=[],
    )


def test_without_an_outgroup_the_copies_are_byte_identical(tmp_path: Path):
    out = tmp_path / "sim"
    out.mkdir()
    rows = copy_model_graphs(_config(tmp_path, [0, 1], None), out)

    assert (out / "model_tree_1.txt").read_text() == TREES[0] + "\n"
    assert (out / "model_networks" / "net1-1.txt").read_text() == NETWORK
    assert all(r["outgroup_label"] is None and r["outgroup_seed"] is None for r in rows)


def test_the_registry_points_at_the_copies(tmp_path: Path):
    # The simulator reads the registered path, so a registered source would
    # leave the graft out of every network dataset.
    out = tmp_path / "sim"
    out.mkdir()
    rows = copy_model_graphs(_config(tmp_path, [0, 1], "OUT"), out)

    assert {Path(r["path"]).parent for r in rows} == {out, out / "model_networks"}
    assert all("OUT" in Path(r["path"]).read_text() for r in rows)


def test_base_trees_are_written_even_when_only_networks_are_simulated(tmp_path: Path):
    out = tmp_path / "sim"
    out.mkdir()
    rows = copy_model_graphs(_config(tmp_path, [1], "OUT"), out)
    assert sorted((r["horizontal_edges"], r["model_tree"]) for r in rows) == [
        (0, 1),
        (0, 2),
        (1, 1),
        (1, 2),
    ]


def test_a_base_tree_keeps_one_graft_across_horizontal_edges(tmp_path: Path):
    out = tmp_path / "sim"
    out.mkdir()
    rows = copy_model_graphs(_config(tmp_path, [0, 1], "OUT"), out)
    grafts = {
        (r["horizontal_edges"], r["model_tree"]): (
            r["outgroup_seed"],
            r["ingroup_stem_length"],
            r["outgroup_branch_length"],
        )
        for r in rows
    }
    assert grafts[(0, 1)] == grafts[(1, 1)]
    assert grafts[(0, 1)] != grafts[(0, 2)]

    # The tree and the network built on it carry the same grafted base tree.
    tree = (out / "model_tree_1.txt").read_text().strip().rstrip(";")
    network_tree = (out / "model_networks" / "net1-1.txt").read_text().splitlines()[0]
    assert tree == network_tree


def test_contact_times_shift_by_the_recorded_stem(tmp_path: Path):
    out = tmp_path / "sim"
    out.mkdir()
    rows = copy_model_graphs(_config(tmp_path, [1], "OUT"), out)
    row = next(r for r in rows if (r["horizontal_edges"], r["model_tree"]) == (1, 1))
    stem = row["ingroup_stem_length"]
    assert stem is not None

    contact = Path(row["path"]).read_text().splitlines()[1]
    clade_a, clade_b, time, strength = contact.split(";")
    assert (clade_a, clade_b, strength) == ("t1", "(t3:0.1,t4:0.2)", "0.19")
    assert float(time) == pytest.approx(0.35 + stem)


def test_rows_fit_the_registry_schema(tmp_path: Path):
    out = tmp_path / "sim"
    out.mkdir()
    rows = copy_model_graphs(_config(tmp_path, [0, 1], "OUT"), out)
    df = pl.DataFrame(data=rows, schema=MODEL_GRAPH_REGISTRY)
    assert df.height == 4
    assert df["outgroup_label"].to_list() == ["OUT"] * 4
