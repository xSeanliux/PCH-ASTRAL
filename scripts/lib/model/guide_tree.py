"""The run space: which trees can guide a network search."""

from typing import Final, Literal

from scripts.lib.model.methods import TreeInferenceMethod

TRUE_TREE: Final = "true_tree"
GuideTree = TreeInferenceMethod | Literal["true_tree"]
# A guide names a method, not a config: MethodConfig holds one config per method.
GUIDE_TREES: Final[frozenset[GuideTree]] = frozenset({*TreeInferenceMethod, TRUE_TREE})

# Rooted binary only. mp is a majority consensus (polytomies), ga is unrooted,
# TREE-QMC can emit polytomies; CAMUS rejects all three.
CAMUS_GUIDE_TREES: Final[frozenset[GuideTree]] = frozenset(
    {TreeInferenceMethod.PCH_ASTRAL3, TreeInferenceMethod.PCH_WASTRAL, TRUE_TREE}
)
# Binary: the guide roots every quartet; a resolved polytomy would root them arbitrarily.
# Rooting is free: every guide is rooted on the outgroup (ga's MCC tree is unrooted).
PHYLONET_MPL_GUIDE_TREES: Final[frozenset[GuideTree]] = CAMUS_GUIDE_TREES | {
    TreeInferenceMethod.GA
}
