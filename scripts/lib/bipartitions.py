import sys
from scripts.lib.types import Taxon


class BipartitionSet:
    taxon_set: frozenset[Taxon]
    bipartitions: set[frozenset[Taxon]]

    def __init__(
        self,
        taxon_set: frozenset[Taxon],
        bipartitions: set[frozenset[Taxon]] = set(),
    ):
        self.taxon_set = taxon_set
        for bp in bipartitions:
            self.add_bipartition(bp)

    def add_bipartition(self, taxa: frozenset[Taxon]):
        """
        adds a bipartition to the taxon set. taxa contains all the taxa on one side.
        """
        assert len(self.taxon_set - taxa) == 0, (
            f"taxa should be a subset of the list of taxa. Extra: {self.taxon_set - taxa}"
        )

        self.bipartitions.add(taxa)

    def print_bipartition_set(self, outfile=sys.stdout):
        for bp in self.bipartitions:
            lhs = ",".join(bp)
            rhs = ",".join(self.taxon_set - bp)
            print(f"(({lhs}),({rhs}));", file=outfile)

    def merge(self, other: "BipartitionSet") -> "BipartitionSet":
        assert other.taxon_set == self.taxon_set, (
            f"merge must have the same taxon set. Found: {other.taxon_set=} vs {self.taxon_set=}"
        )
        return BipartitionSet(
            taxon_set=self.taxon_set,
            bipartitions=self.bipartitions | other.bipartitions,
        )
