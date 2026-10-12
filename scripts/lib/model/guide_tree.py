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

# Rooted binary only. mp is a majority consensus (polytomies), ga is unrooted,
# TREE-QMC can emit polytomies; CAMUS rejects all three.
CAMUS_GUIDE_TREES: Final[frozenset[GuideTree]] = frozenset(
    {TreeInferenceMethod.PCH_ASTRAL3, TreeInferenceMethod.PCH_WASTRAL, TRUE_TREE}
)
