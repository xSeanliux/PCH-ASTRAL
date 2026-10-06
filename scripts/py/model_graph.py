"""Print `<horizontal_edges> <outgroup_label>` of the model graph a simulated
dataset was simulated from; `none` when the experiment has no outgroup.

    python3 -m scripts.py.model_graph --input <dataset.csv>
"""

import argparse
from pathlib import Path

import polars as pl

from scripts.lib.inference import registry
from scripts.py.cli.schemata import MODEL_GRAPH_REGISTRY, SIMULATED_DATA_REGISTRY_SCHEMA


def find_dataset_model_graph(
    input_csv: Path, is_base_tree: bool = False
) -> pl.DataFrame:
    """The `model_graph_registry.csv` row a simulated dataset was simulated from.

    :param is_base_tree: return its model tree's base tree (h = 0) row instead.
    :raises ValueError: if the dataset is outside an experiment, or it or its
        model graph is not registered.
    """
    sim_dirs = [f / "simulation_data" for f in input_csv.resolve().parents]
    sim_dir = next(
        (d for d in sim_dirs if (d / "simulated_data_registry.csv").is_file()), None
    )
    if sim_dir is None:
        raise ValueError(f"{input_csv} is not inside an experiment's simulation_data")
    want = registry.canonical_path(input_csv.resolve())
    datasets = pl.read_csv(
        sim_dir / "simulated_data_registry.csv", schema=SIMULATED_DATA_REGISTRY_SCHEMA
    ).filter(
        pl.col("path").map_elements(
            lambda p: registry.canonical_path(Path(p).resolve()) == want,
            return_dtype=pl.Boolean,
        )
    )
    if is_base_tree:
        datasets = datasets.with_columns(horizontal_edges=pl.lit(0, pl.Int64))
    graphs = pl.read_csv(
        sim_dir / "model_graph_registry.csv", schema=MODEL_GRAPH_REGISTRY
    )
    rows = datasets.select("horizontal_edges", "model_tree").join(
        graphs, on=["horizontal_edges", "model_tree"]
    )
    if rows.height == 0:
        raise ValueError(f"No registered model graph for {input_csv}")
    return rows.head(1)


def main() -> None:
    """Print the dataset's reticulation count and outgroup."""
    parser = argparse.ArgumentParser(
        description="Print a dataset's reticulation count and outgroup."
    )
    parser.add_argument("--input", type=Path, required=True)
    row = find_dataset_model_graph(parser.parse_args().input)
    print(row["horizontal_edges"][0], row["outgroup_label"][0] or "none")


if __name__ == "__main__":
    main()
