"""Print `<horizontal_edges> <outgroup_label>` of the model graph a simulated
dataset was simulated from; `none` when the experiment has no outgroup.

    python3 -m scripts.py.model_graph --input <dataset.csv>
"""

import argparse
from pathlib import Path

from scripts.lib.model.model_graph import find_dataset_model_graph


def main() -> None:
    """Print `<horizontal_edges> <outgroup_label|none>` for `--input` (SNaQ's hmax).

    Base-tree callers use `scoring.resolve_reference_newick`.

    :raises ValueError: as `find_dataset_model_graph`.
    """
    parser = argparse.ArgumentParser(
        description="Print a dataset's reticulation count and outgroup."
    )
    parser.add_argument("--input", type=Path, required=True)
    graph = find_dataset_model_graph(parser.parse_args().input)
    print(graph.horizontal_edges, graph.outgroup_label or "none")


if __name__ == "__main__":
    main()
