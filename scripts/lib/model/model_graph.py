"""Which model graph a simulated dataset came from.

A model graph is the base tree (h = 0) or contact network (h > 0) a dataset was
simulated from. Read from `simulation_data/simulated_data_registry.csv` (dataset →
key) and `simulation_data/model_graph_registry.csv` (key → graph file).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Self

import polars as pl

from scripts.py.cli.schemata import MODEL_GRAPH_REGISTRY, SIMULATED_DATA_REGISTRY_SCHEMA


@dataclass(frozen=True)
class ModelGraph:
    """One `model_graph_registry.csv` row.

    :ivar horizontal_edges: reticulation count; 0 is the base tree.
    :ivar model_tree: base tree index.
    :ivar path: graph file, e.g. `net2-1.txt` or `model_tree_1.txt`.
    :ivar outgroup_label: outgroup leaf; None when the experiment has no outgroup.
    """

    horizontal_edges: int
    model_tree: int
    path: Path
    outgroup_label: str | None  # None when the experiment has no outgroup

    @classmethod
    def from_registry(
        cls, experiment_folder: Path, horizontal_edges: int, model_tree: int
    ) -> Self:
        """Read the registered model graph for a key; e.g. (2, 1) → `net2-1.txt`,
        base tree (0, 1) → `model_tree_1.txt`.

        :param experiment_folder: experiment root, holding `simulation_data/`.
        :param horizontal_edges: reticulation count; 0 for the base tree.
        :param model_tree: base tree index.
        :returns: the graph's registry row.
        :raises ValueError: if the registry has zero or several such graphs.
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
        return cls(
            horizontal_edges, model_tree, Path(df["path"][0]), df["outgroup_label"][0]
        )

    @classmethod
    def from_dataset(cls, input_csv: Path) -> Self:
        """Read the model graph a simulated dataset was simulated from; e.g.
        `sim_2_1_1.csv` → (2, 1) → `net2-1.txt`. Base-tree callers use
        `scoring.resolve_reference_newick`.

        :param input_csv: dataset CSV under an experiment's `simulation_data/`.
        :returns: the dataset's own graph (h as simulated, not the base tree).
        :raises ValueError: as `find_dataset_key`, or `from_registry` if the graph
            is not registered exactly once.
        """
        return cls.from_registry(*find_dataset_key(input_csv))


def find_dataset_key(input_csv: Path) -> tuple[Path, int, int]:
    """The model graph key of a simulated dataset; e.g. `sim_2_1_1.csv` →
    (<experiment>, 2, 1).

    :param input_csv: dataset CSV under an experiment's `simulation_data/`.
    :returns: `(experiment_folder, horizontal_edges, model_tree)`.
    :raises ValueError: if the dataset is outside an experiment, unregistered, or
        its registry rows disagree on the key.
    """
    sim_dirs = [f / "simulation_data" for f in input_csv.resolve().parents]
    sim_dir = next(
        (d for d in sim_dirs if (d / "simulated_data_registry.csv").is_file()), None
    )
    if sim_dir is None:
        raise ValueError(f"{input_csv} is not inside an experiment's simulation_data")
    want = input_csv.expanduser().resolve()
    # The registry can repeat a dataset's row verbatim; only disagreement is an error.
    keys = (
        pl.read_csv(
            sim_dir / "simulated_data_registry.csv",
            schema=SIMULATED_DATA_REGISTRY_SCHEMA,
        )
        .filter(
            pl.col("path").map_elements(
                lambda p: Path(p).expanduser().resolve() == want,
                return_dtype=pl.Boolean,
            )
        )
        .select("horizontal_edges", "model_tree")
        .unique()
    )
    if keys.height != 1:
        raise ValueError(
            f"No registered dataset {input_csv}"
            if keys.height == 0
            else f"{keys.height} conflicting registry rows for {input_csv}"
        )
    return sim_dir.parent, keys["horizontal_edges"][0], keys["model_tree"][0]
