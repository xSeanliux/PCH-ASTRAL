from pathlib import Path

import polars as pl
import pytest

from scripts.lib.model.model_graph import (
    ModelGraph,
    find_dataset_model_graph,
    find_model_graph,
)


def _experiment(tmp_path: Path, dataset_rows: list[int], graph_rows: int = 1) -> Path:
    """An experiment whose `sim_2_1_1.csv` is registered once per entry of
    `dataset_rows` (its h), with `graph_rows` copies of `net2-1.txt`."""
    sim = tmp_path / "simulation_data"
    condition = sim / "simulated_data" / "high_0.1_4_80"
    condition.mkdir(parents=True)
    dataset = condition / "sim_2_1_1.csv"
    dataset.touch()
    n = len(dataset_rows)
    pl.DataFrame(
        {
            "poly_level": ["high"] * n,
            "character_count": [80] * n,
            "min_tree_height": [4] * n,
            "homoplasy_factor": [0.1] * n,
            "horizontal_edges": dataset_rows,
            "model_tree": [1] * n,
            "replica": [1] * n,
            "path": [str(dataset)] * n,
        }
    ).write_csv(sim / "simulated_data_registry.csv")
    pl.DataFrame(
        {
            "horizontal_edges": [0] + [2] * graph_rows,
            "model_tree": [1] * (graph_rows + 1),
            "path": [str(sim / "model_tree_1.txt")]
            + [str(sim / "net2-1.txt")] * graph_rows,
            "outgroup_label": ["OUT"] * (graph_rows + 1),
        },
        schema_overrides={"outgroup_label": pl.String},
    ).write_csv(sim / "model_graph_registry.csv")
    return dataset


def test_find_model_graph_rejects_duplicates(tmp_path: Path):
    _experiment(tmp_path, [2], graph_rows=2)
    with pytest.raises(ValueError, match="2 model graphs"):
        find_model_graph(tmp_path, 2, 1)


def test_a_dataset_finds_its_own_model_graph(tmp_path: Path):
    dataset = _experiment(tmp_path, [2])
    sim = tmp_path / "simulation_data"
    assert find_dataset_model_graph(dataset) == ModelGraph(
        2, 1, sim / "net2-1.txt", "OUT"
    )


def test_identical_duplicate_dataset_rows_are_ok(tmp_path: Path):
    dataset = _experiment(tmp_path, [2, 2])
    assert find_dataset_model_graph(dataset).horizontal_edges == 2


def test_conflicting_duplicate_dataset_rows_are_an_error(tmp_path: Path):
    dataset = _experiment(tmp_path, [2, 1])
    with pytest.raises(ValueError, match="2 conflicting"):
        find_dataset_model_graph(dataset)


def test_an_unregistered_dataset_is_an_error(tmp_path: Path):
    dataset = _experiment(tmp_path, [2])
    with pytest.raises(ValueError, match="No registered"):
        find_dataset_model_graph(dataset.with_name("sim_9_9_9.csv"))


def test_a_dataset_outside_an_experiment_is_an_error(tmp_path: Path):
    with pytest.raises(ValueError, match="not inside an experiment"):
        find_dataset_model_graph(tmp_path / "loose.csv")
