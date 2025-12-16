# Given a list of quartets and a tree in Newick format
# compute the number of quartets that agree with the tree.
# ASTRAL has this functionality - this is an alternative reimplementation to check it.
# Uses DFS order. 

from Bio import Phylo
from typing import Dict, Tuple

class QuartetScorer:
    def __init__(
        self,
        tree: Phylo.BaseTree.TreeMixin, 
    ):
        self.tree = tree
        taxa_names = [c.name for c in tree.get_terminals()]
        self.taxa_dfs_ord = {
            n: i for i, n in enumerate(taxa_names)
        }

    def test_quartet(
        self,
        q: Tuple[str, str, str, str]
    ) -> bool:
        a, b, c, d = q
        l = self.tree.common_ancestor([a, b, c, d])
        l1 = self.tree.common_ancestor([a, b])
        l2 = self.tree.common_ancestor([c, d])

        def clade_eq(c1, c2):

            def clade_hash(c):
                terminals = c.get_terminals()
                return "|".join([ c.name for c in terminals ])
            return clade_hash(c1) == clade_hash(c2)

        return not (
            clade_eq(l, l2) and (
                clade_eq(self.tree.common_ancestor([a, b, c]), l1) or 
                clade_eq(self.tree.common_ancestor([a, b, d]), l1)
            ) or 
            clade_eq(l, l1) and (
                clade_eq(self.tree.common_ancestor([c, d, a]), l2) or 
                clade_eq(self.tree.common_ancestor([c, d, b]), l2)
            )
        )





