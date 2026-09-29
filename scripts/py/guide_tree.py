"""Print the guide tree for one dataset: topology only, rooted on the outgroup.

    python3 -m scripts.py.guide_tree --guide astral3 --input <dataset.csv> --output <output_dir>

A method guide is that method's point estimate for the dataset. `true_tree` is the
dataset's base tree. The outgroup is the one recorded for the dataset's model tree.
"""

import argparse
from io import StringIO
from pathlib import Path

import polars as pl
from Bio import Phylo
from Bio.Phylo.BaseTree import Clade

from scripts.lib.experiment import CamusConfig
from scripts.lib.inference import registry
from scripts.lib.inference.runners import TREE_RUNNERS
from scripts.py.cli.schemata import MODEL_GRAPH_REGISTRY, SIMULATED_DATA_REGISTRY_SCHEMA

GuideTree = CamusConfig.GuideTree


def _topology(clade: Clade) -> str:
    if clade.is_terminal():
        assert clade.name is not None, "a leaf has no name"
        return clade.name
    return "(" + ",".join(_topology(c) for c in clade.clades) + ")"


def rooted_topology(newick: str, outgroup: str | None) -> str:
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
    return _topology(tree.root) + ";"


def experiment_of(input_csv: Path) -> Path:
    """The experiment folder a simulated dataset belongs to."""
    for folder in input_csv.resolve().parents:
        if (folder / "simulation_data" / "simulated_data_registry.csv").is_file():
            return folder
    raise ValueError(f"{input_csv} is not inside an experiment's simulation_data")


def model_tree_of(experiment: Path, input_csv: Path) -> int:
    sim = pl.read_csv(
        experiment / "simulation_data" / "simulated_data_registry.csv",
        schema=SIMULATED_DATA_REGISTRY_SCHEMA,
    )
    want = registry.canonical_path(input_csv.resolve())
    for row in sim.iter_rows(named=True):
        if registry.canonical_path(Path(row["path"]).resolve()) == want:
            return int(row["model_tree"])
    raise ValueError(f"{input_csv} is not in the simulation registry")


def base_tree_of(experiment: Path, model_tree: int) -> tuple[str, str | None]:
    """(newick, outgroup label or None) of a model tree's base tree."""
    reg = experiment / "simulation_data" / "model_graph_registry.csv"
    rows = pl.read_csv(reg, schema=MODEL_GRAPH_REGISTRY).filter(
        (pl.col("horizontal_edges") == 0) & (pl.col("model_tree") == model_tree)
    )
    if rows.height == 0:
        raise ValueError(f"No base tree for model_tree={model_tree} in {reg}")
    row = rows.row(0, named=True)
    return Path(row["path"]).read_text().strip(), row["outgroup"]


def guide_newick(guide: GuideTree, input_csv: Path, output_dir: Path) -> str:
    experiment = experiment_of(input_csv)
    base_tree, outgroup = base_tree_of(experiment, model_tree_of(experiment, input_csv))
    method = guide.dependency
    if method is None:
        return rooted_topology(base_tree, outgroup)
    estimate = TREE_RUNNERS[method].point_estimate_path(output_dir, input_csv.stem)
    return rooted_topology(estimate.read_text().strip(), outgroup)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print one dataset's guide tree, rooted on the outgroup."
    )
    parser.add_argument("--guide", type=GuideTree, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(guide_newick(args.guide, args.input, args.output))


if __name__ == "__main__":
    main()
