"""Print the PhyloNet NEXUS that runs PhyloNet-MPL(FT) on one simulated dataset.

    python3 -m scripts.py.phylonet_mpl_nexus --input <dataset.csv> \
        --output <output_dir> --result <networks.txt> [--procs N]

Mirrors the CAMUS paper's wrapper (`InferNetwork_MPL (all) k -s st -fs -pl N`):
k = the dataset's contact event count, start tree = pch_wastral rooted on the
outgroup, fixed.
"""

import argparse
from collections import Counter
from pathlib import Path

from scripts.lib.model.methods import TreeInferenceMethod
from scripts.lib.pch import PCH_W
from scripts.lib.types import Dataset, Quartet
from scripts.py.guide_tree import build_guide_newick
from scripts.py.model_graph import find_dataset_model_graph


def root_quartets(quartets: Counter[Quartet], outgroup: str) -> list[str]:
    """Each quartet holding `outgroup`, rooted on it, once per unit of weight.

    MPL needs rooted gene trees; a quartet without the outgroup has no root.
    """
    rooted: list[str] = []
    for q, w in quartets.items():
        a, b, c, d = q._quartet  # ((a,b),(c,d))
        if outgroup in (a, b):
            a, b, c, d = c, d, a, b
        if outgroup not in (c, d):
            continue
        sister = d if c == outgroup else c
        rooted += [f"((({a},{b}),{sister}),{outgroup});"] * w
    return rooted


def build_nexus(input_csv: Path, output_dir: Path, result: Path, procs: int) -> str:
    """The NEXUS command file for one dataset.

    :raises ValueError: if the experiment simulated no outgroup.
    """
    graph = find_dataset_model_graph(input_csv)
    k, outgroup = graph["horizontal_edges"][0], graph["outgroup_label"][0]
    if outgroup is None:
        raise ValueError("PhyloNet-MPL needs simulation.outgroup_label set")
    start = build_guide_newick(
        TreeInferenceMethod.PCH_WASTRAL, input_csv, output_dir, outgroup
    )
    gts = root_quartets(PCH_W.get_quartets(Dataset.from_path(input_csv)), outgroup)
    trees = "\n".join(f"Tree gt{i} = {t}" for i, t in enumerate(gts))
    # ponytail: PhyloNet defaults (-x 10 runs, no -o/-po), as the paper ran it.
    return (
        f"#NEXUS\nBEGIN NETWORKS;\nNetwork st = {start}\nEND;\n"
        f"BEGIN TREES;\n{trees}\nEND;\n"
        f"BEGIN PHYLONET;\nInferNetwork_MPL (all) {k} -s st -fs -pl {procs} {result};\nEND;\n"
    )


def main() -> None:
    """Print the NEXUS for the dataset named on the command line."""
    parser = argparse.ArgumentParser(description="Print a PhyloNet-MPL(FT) NEXUS.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--procs", type=int, default=1)
    args = parser.parse_args()
    print(build_nexus(args.input, args.output, args.result, args.procs), end="")


if __name__ == "__main__":
    main()
