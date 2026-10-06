"""Print the guide tree for one dataset: binary topology, rooted on the outgroup.

    python3 -m scripts.py.guide_tree --guide pch_astral3 --input <dataset.csv> \
        --output <output_dir> --outgroup <label>

A method guide is that method's point estimate for the dataset, so any dataset
works. `true_tree` is the base tree of a simulated dataset.
"""

import argparse
from io import StringIO
from pathlib import Path

import polars as pl
from Bio import Phylo

from scripts.lib.inference import registry
from scripts.lib.inference.runners import METHOD_TO_RUNNER_CLASS
from scripts.lib.model.guide_tree import SUPPORTED_GUIDE_TREES, TRUE_TREE, GuideTree
from scripts.lib.model.methods import TreeInferenceMethod
from scripts.lib.utils import resolve_polytomies, tree_to_newick
from scripts.py.cli.schemata import MODEL_GRAPH_REGISTRY, SIMULATED_DATA_REGISTRY_SCHEMA


def root_topology(newick: str, outgroup_label: str) -> str:
    """`newick` as a binary topology, rooted on `outgroup_label`.

    Polytomies are resolved arbitrarily (seeded): CAMUS needs a binary guide.

    :raises ValueError: if the outgroup is not a leaf of the tree.
    """
    tree = Phylo.read(StringIO(newick), "newick")
    if outgroup_label not in {t.name for t in tree.get_terminals()}:
        raise ValueError(f"outgroup {outgroup_label!r} is not in the tree")
    tree.root_with_outgroup(outgroup_label)
    resolve_polytomies(tree)
    return tree_to_newick(tree).strip()


def find_base_tree(input_csv: Path) -> str:
    """Newick of the base tree a simulated dataset was simulated from.

    :raises ValueError: if the dataset is outside an experiment, or it or its base
        tree is not registered.
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
    base_trees = pl.read_csv(
        sim_dir / "model_graph_registry.csv", schema=MODEL_GRAPH_REGISTRY
    ).filter(pl.col("horizontal_edges") == 0)
    rows = datasets.select("model_tree").join(base_trees, on="model_tree")
    if rows.height == 0:
        raise ValueError(f"No registered base tree for {input_csv}")
    return Path(rows["path"][0]).read_text().strip()


def build_guide_newick(
    guide: GuideTree, input_csv: Path, output_dir: Path, outgroup_label: str
) -> str:
    """The guide tree for one dataset, rooted on `outgroup_label`.

    :param guide: `true_tree` or the tree method whose estimate guides.
    """
    if guide == TRUE_TREE:
        return root_topology(find_base_tree(input_csv), outgroup_label)
    estimate = METHOD_TO_RUNNER_CLASS[guide].get_point_estimate_path(
        output_dir, input_csv.stem
    )
    assert estimate is not None, f"{guide} has no point estimate"
    return root_topology(estimate.read_text().strip(), outgroup_label)


def main() -> None:
    """Print the guide tree named on the command line."""
    parser = argparse.ArgumentParser(
        description="Print one dataset's guide tree, rooted on the outgroup."
    )
    parser.add_argument(
        "--guide", choices=sorted(map(str, SUPPORTED_GUIDE_TREES)), required=True
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--outgroup", required=True)
    args = parser.parse_args()
    guide = TRUE_TREE if args.guide == TRUE_TREE else TreeInferenceMethod(args.guide)
    print(build_guide_newick(guide, args.input, args.output, args.outgroup))


if __name__ == "__main__":
    main()
