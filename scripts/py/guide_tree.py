"""Print the guide tree for one dataset: topology only, rooted on the outgroup.

    python3 -m scripts.py.guide_tree --guide pch_astral3 --input <dataset.csv> --output <output_dir>

A method guide is that method's point estimate for the dataset. `true_tree` is the
dataset's base tree. The outgroup is the one recorded for the dataset's model tree.
"""

import argparse
from io import StringIO
from pathlib import Path

import polars as pl
from Bio import Phylo
from Bio.Phylo.BaseTree import Clade

from scripts.lib.inference import registry
from scripts.lib.inference.runners import METHOD_TO_RUNNER_CLASS
from scripts.lib.model.guide_tree import SUPPORTED_GUIDE_TREES, TRUE_TREE, GuideTree
from scripts.py.cli.schemata import MODEL_GRAPH_REGISTRY, SIMULATED_DATA_REGISTRY_SCHEMA


def _write_topology(clade: Clade) -> str:
    """`clade` as Newick without lengths or support values, no terminator."""
    if clade.is_terminal():
        assert clade.name is not None, "a leaf has no name"
        return clade.name
    return "(" + ",".join(_write_topology(c) for c in clade.clades) + ")"


def root_topology(newick: str, outgroup: str | None) -> str:
    """`newick` without lengths or support values, rooted on `outgroup` if given.

    Polytomies are kept: resolving one would invent a split the data never
    supported, and CAMUS drops every quartet the guide tree displays.
    """
    tree = Phylo.read(StringIO(newick), "newick")
    if outgroup is not None:
        leaves = {t.name for t in tree.get_terminals()}
        if outgroup not in leaves:
            raise ValueError(f"outgroup {outgroup!r} is not in the tree")
        tree.root_with_outgroup(outgroup)
    return _write_topology(tree.root) + ";"


def find_experiment(input_csv: Path) -> Path:
    """The experiment folder a simulated dataset belongs to."""
    for folder in input_csv.resolve().parents:
        if (folder / "simulation_data" / "simulated_data_registry.csv").is_file():
            return folder
    raise ValueError(f"{input_csv} is not inside an experiment's simulation_data")


def find_model_tree(experiment: Path, input_csv: Path) -> int:
    """The model tree a dataset was simulated from."""
    sim = pl.read_csv(
        experiment / "simulation_data" / "simulated_data_registry.csv",
        schema=SIMULATED_DATA_REGISTRY_SCHEMA,
    )
    want = registry.canonical_path(input_csv.resolve())
    for row in sim.iter_rows(named=True):
        if registry.canonical_path(Path(row["path"]).resolve()) == want:
            return int(row["model_tree"])
    raise ValueError(f"{input_csv} is not in the simulation registry")


def find_base_tree(experiment: Path, model_tree: int) -> tuple[str, str | None]:
    """(newick, outgroup label or None) of a model tree's base tree."""
    reg = experiment / "simulation_data" / "model_graph_registry.csv"
    rows = pl.read_csv(reg, schema=MODEL_GRAPH_REGISTRY).filter(
        (pl.col("horizontal_edges") == 0) & (pl.col("model_tree") == model_tree)
    )
    if rows.height == 0:
        raise ValueError(f"No base tree for model_tree={model_tree} in {reg}")
    row = rows.row(0, named=True)
    return Path(row["path"]).read_text().strip(), row["outgroup"]


def build_guide_newick(guide: GuideTree, input_csv: Path, output_dir: Path) -> str:
    """The rooted guide tree for one dataset.

    :param guide: `true_tree` or the tree method whose estimate guides.
    :raises AssertionError: if the method has no point estimate.
    """
    experiment = find_experiment(input_csv)
    base_tree, outgroup = find_base_tree(
        experiment, find_model_tree(experiment, input_csv)
    )
    if guide == TRUE_TREE:
        return root_topology(base_tree, outgroup)
    estimate = METHOD_TO_RUNNER_CLASS[guide].get_point_estimate_path(
        output_dir, input_csv.stem
    )
    assert estimate is not None, f"{guide} has no point estimate"
    return root_topology(estimate.read_text().strip(), outgroup)


def parse_guide(value: str) -> GuideTree:
    """Parse `--guide`: `true_tree` or a supported tree method value.

    :raises argparse.ArgumentTypeError: if unknown or unsupported.
    """
    value_to_guide = {str(g): g for g in SUPPORTED_GUIDE_TREES}
    if value not in value_to_guide:
        raise argparse.ArgumentTypeError(
            f"{value!r} is not a guide; use {sorted(value_to_guide)}"
        )
    return value_to_guide[value]


def main() -> None:
    """Print the guide tree named on the command line."""
    parser = argparse.ArgumentParser(
        description="Print one dataset's guide tree, rooted on the outgroup."
    )
    parser.add_argument("--guide", type=parse_guide, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(build_guide_newick(args.guide, args.input, args.output))


if __name__ == "__main__":
    main()
