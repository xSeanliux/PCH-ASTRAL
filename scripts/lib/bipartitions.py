import sys
from scripts.lib.types import Taxon, Dataset, State
from scripts.lib.utils import tree_to_newick
from typing import Literal
from collections import defaultdict
from Bio.Phylo.BaseTree import Tree, Clade
from Bio.Phylo.NewickIO import write


TreeFormat = Literal["newick", "nexus"]


class ConstraintTrees:
    treeset: set[Tree]

    def __init__(
        self,
        trees: set[Tree] = set(),
    ):
        self.treeset = trees

    def add_trees(self, trees: set[Tree]):
        """
        adds a bipartition to the taxon set. taxa contains all the taxa on one side.
        """
        self.treeset.update(trees)

    def write(self, outfile=sys.stdout):
        write(
            trees=sorted(self.treeset, key=tree_to_newick),
            handle=outfile,
            plain=True,
        )


def constraint_trees_from_dataset(dataset: Dataset) -> set[Tree]:
    treeset: set[Tree] = set()
    taxon_set = set(dataset.names)
    for chr in dataset.chrs:
        state_to_taxon: dict[State, set[Taxon]] = defaultdict(set)
        for t, ss in chr.features.items():
            for s in ss:
                state_to_taxon[s].add(t)

        for ts in state_to_taxon.values():
            if len(ts) == len(taxon_set):
                continue
            tree = Tree.from_clade(
                Clade(
                    clades=[
                        Clade(clades=[Clade(name=t) for t in sorted(ts)]),
                        Clade(clades=[Clade(name=t) for t in sorted(taxon_set - ts)]),
                    ]
                )
            )
            treeset.add(tree)

    return treeset
