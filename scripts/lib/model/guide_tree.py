"""The run space: which trees can guide a network search."""

from typing import Final, Literal

from scripts.lib.model.methods import TreeInferenceMethod

TRUE_TREE: Final = "true_tree"
GuideTree = TreeInferenceMethod | Literal["true_tree"]
# A guide names a method, not a config: MethodConfig holds one config per method.
GUIDE_TREES: Final[frozenset[GuideTree]] = frozenset({*TreeInferenceMethod, TRUE_TREE})

# Species trees only. A tree of blobs' polytomies are blobs, not uncertainty: resolving
# them gives an arbitrary start tree.
SNAQ_GUIDE_TREES: Final[frozenset[GuideTree]] = GUIDE_TREES - {
    TreeInferenceMethod.TOB_QMC
}

# Rooted binary only. mp is a majority consensus (polytomies) and ga is unrooted;
# CAMUS rejects both. TREE-QMC's rare polytomy is resolved arbitrarily
# (`scripts/py/guide_tree.py`).
CAMUS_GUIDE_TREES: Final[frozenset[GuideTree]] = frozenset(
    {
        TreeInferenceMethod.PCH_ASTRAL3,
        TreeInferenceMethod.PCH_WASTRAL,
        TreeInferenceMethod.PCH_W_TREE_QMC,
        TRUE_TREE,
    }
)


def parse_guide(name: str) -> GuideTree:
    """The guide named `name`, e.g. a CLI argument.

    :raises ValueError: if `name` is no guide.
    """
    return TRUE_TREE if name == TRUE_TREE else TreeInferenceMethod(name)
