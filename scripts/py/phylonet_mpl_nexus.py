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
from pathlib import Path

from Bio import Phylo

from scripts.lib.model.guide_tree import (
    PHYLONET_MPL_GUIDE_TREES,
    GuideTree,
    parse_guide,
)
from scripts.lib.model.model_graph import ModelGraph
from scripts.lib.pch import PCH_W
from scripts.lib.types import Dataset, Quartet
from scripts.py.guide_tree import build_guide_newick


def root_quartets(quartets: Counter[Quartet], guide_newick: str) -> Counter[str]:
    """Each quartet rooted as `guide_newick` roots its four taxa, with its weight.

    MPL reads rooted triples from each gene tree's root, so an unrooted quartet needs
    one. The guide's first split among the four taxa places it: 1|3 → on that taxon's
    pendant edge; 2|2 → on the quartet's central edge, even if the quartet disagrees
    with the guide there. A quartet with the outgroup is rooted on it.
    """
    tree = Phylo.read(StringIO(guide_newick), "newick")
    leaves = {id(c): {t.name for t in c.get_terminals()} for c in tree.find_clades()}

    rooted: Counter[str] = Counter()
    for q, w in quartets.items():
        (a, b), (c, d) = q.as_tuples()
        taxa = {a, b, c, d}
        # The guide is binary: its LCA of the four splits them 1|3 or 2|2.
        lca = tree.common_ancestor(*taxa)
        lone = [s for child in lca.clades if len(s := leaves[id(child)] & taxa) == 1]
        if not lone:  # 2|2
            newick = f"(({a},{b}),({c},{d}));"
        else:  # 1|3: `x` splits off first
            ((x,),) = lone
            if x in (c, d):
                a, b, c, d = c, d, a, b
            sister = b if x == a else a
            newick = f"((({c},{d}),{sister}),{x});"
        rooted[newick] += w
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
    # [&W w]: PhyloNet sums a tree's weights, as if it were repeated w times.
    trees = "\n".join(
        f"Tree gt{i} = [&W {w}] {t}" for i, (t, w) in enumerate(gts.items())
    )
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
    guide = parse_guide(args.guide)
    print(build_nexus(args.input, args.output, guide, args.result, args.procs), end="")


if __name__ == "__main__":
    main()
