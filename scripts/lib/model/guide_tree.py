"""The run space: which trees can guide a network search."""

from typing import Final, Literal

from scripts.lib.model.methods import TreeInferenceMethod

TRUE_TREE: Final = "true_tree"
GuideTree = TreeInferenceMethod | Literal["true_tree"]

# Rooted binary only. mp is a majority consensus (polytomies), ga is unrooted,
# TREE-QMC can emit polytomies; CAMUS rejects all three.
# A guide names a method, not a config: MethodConfig holds one config per method.
SUPPORTED_GUIDE_TREES: Final[frozenset[GuideTree]] = frozenset(
    {TreeInferenceMethod.PCH_ASTRAL3, TreeInferenceMethod.PCH_WASTRAL, TRUE_TREE}
)
