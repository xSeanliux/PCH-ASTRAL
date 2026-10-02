from enum import StrEnum

from scripts.lib.model.methods import TreeInferenceMethod


class GuideTree(StrEnum):
    """Which tree constrains the CAMUS network search.

    Membership in `GUIDE_TREE_DEPENDENCY` is the allow-list: a member absent
    from that map is a guide CAMUS cannot accept (see `is_supported`).
    """

    MP = "mp"
    GA = "ga"
    ASTRAL3 = "astral3"
    WASTRAL = "wastral"
    W_TREE_QMC = "w_tree_qmc"
    TRUE_TREE = "true_tree"

    @property
    def is_supported(self) -> bool:
        return self in GUIDE_TREE_DEPENDENCY

    @property
    def dependency(self) -> TreeInferenceMethod | None:
        """The method whose output supplies this guide (None = already have it)."""
        return GUIDE_TREE_DEPENDENCY[self]


# Guide tree -> the method whose output supplies it (None = already have it).
# ONLY these are allowed; absent = CAMUS can't use it. w_tree_qmc is out for now:
# TREE-QMC can emit polytomies, which CAMUS rejects.
# A guide names a method, not a config: MethodConfig holds one config per
# method, so "the astral3 tree" is unique per experiment.
GUIDE_TREE_DEPENDENCY: dict[GuideTree, TreeInferenceMethod | None] = {
    GuideTree.ASTRAL3: TreeInferenceMethod.PCH_ASTRAL3,
    GuideTree.WASTRAL: TreeInferenceMethod.PCH_WASTRAL,
    GuideTree.TRUE_TREE: None,
}
