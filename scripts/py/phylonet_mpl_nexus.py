"""Print the PhyloNet NEXUS that runs PhyloNet-MPL(FT) on one simulated dataset.

    python3 -m scripts.py.phylonet_mpl_nexus --input <dataset.csv> \
        --output <output_dir> --guide <guide> --result <networks.txt> [--procs N]

Mirrors the CAMUS paper's wrapper (`InferNetwork_MPL (all) k -s st -fs -pl N`):
k = the dataset's contact event count, start tree = the guide rooted on the
outgroup. Gene trees: every PCH-W quartet, rooted by the guide (`root_quartets`).
The paper's guide was pch_wastral.
"""

import argparse
from collections import Counter
from io import StringIO
from itertools import combinations, takewhile
from pathlib import Path

from Bio import Phylo

from scripts.lib.model.guide_tree import TRUE_TREE, GuideTree, PHYLONET_MPL_GUIDE_TREES
from scripts.lib.model.methods import TreeInferenceMethod
from scripts.lib.model.model_graph import ModelGraph
from scripts.lib.pch import PCH_W
from scripts.lib.types import Dataset, Quartet
from scripts.py.guide_tree import build_guide_newick


def root_quartets(quartets: Counter[Quartet], guide_newick: str) -> list[str]:
    """Each quartet rooted as `guide_newick` roots its four taxa, once per unit of weight.

    MPL reads rooted triples from each gene tree's root, so an unrooted quartet needs
    one. The guide's first split among the four taxa places it: 1|3 → on that taxon's
    pendant edge; 2|2 → on the quartet's central edge, even if the quartet disagrees
    with the guide there. A quartet with the outgroup is rooted on it.
    """
    tree = Phylo.read(StringIO(guide_newick), "newick")
    path = {
        leaf.name: [id(c) for c in tree.get_path(leaf)] for leaf in tree.get_terminals()
    }

    def lca_depth(x: str, y: str) -> int:
        """Edges from the root to the LCA of `x` and `y`."""
        return sum(1 for _ in takewhile(lambda p: p[0] == p[1], zip(path[x], path[y])))

    rooted: list[str] = []
    for q, w in quartets.items():
        a, b, c, d = q._quartet  # ((a,b),(c,d))
        top = min(lca_depth(x, y) for x, y in combinations((a, b, c, d), 2))
        first = [
            x
            for x in (a, b, c, d)
            if all(lca_depth(x, y) == top for y in (a, b, c, d) if y != x)
        ]
        if not first:  # 2|2
            newick = f"(({a},{b}),({c},{d}));"
        else:  # 1|3: `first[0]` splits off first
            (x,) = first
            if x in (c, d):
                a, b, c, d = c, d, a, b
            sister = b if x == a else a
            newick = f"((({c},{d}),{sister}),{x});"
        rooted += [newick] * w
    return rooted


def build_nexus(
    input_csv: Path, output_dir: Path, guide: GuideTree, result: Path, procs: int
) -> str:
    """The NEXUS command file for one dataset.

    :raises ValueError: if the experiment simulated no outgroup.
    """
    graph = ModelGraph.from_dataset(input_csv)
    k, outgroup = graph.horizontal_edges, graph.outgroup_label
    if outgroup is None:
        raise ValueError("PhyloNet-MPL needs simulation.outgroup_label set")
    start = build_guide_newick(guide, input_csv, output_dir, outgroup)
    gts = root_quartets(PCH_W.get_quartets(Dataset.from_path(input_csv)), start)
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
    parser.add_argument(
        "--guide", choices=sorted(map(str, PHYLONET_MPL_GUIDE_TREES)), required=True
    )
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--procs", type=int, default=1)
    args = parser.parse_args()
    guide = TRUE_TREE if args.guide == TRUE_TREE else TreeInferenceMethod(args.guide)
    print(build_nexus(args.input, args.output, guide, args.result, args.procs), end="")


if __name__ == "__main__":
    main()
