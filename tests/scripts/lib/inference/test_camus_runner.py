import pytest
from pydantic import ValidationError

from scripts.lib.experiment import CamusConfig
from scripts.lib.inference.inference import TreeInferenceMethod
from scripts.lib.inference.runners.camus import CamusRunner

G = CamusConfig.GuideTree


def test_supported_guides_declare_their_dependency():
    # astral3 gates on the upstream method; true_tree is already on disk.
    assert G.ASTRAL3.dependency is TreeInferenceMethod.PCH_ASTRAL3
    assert G.TRUE_TREE.dependency is None


@pytest.mark.parametrize("guide", [G.MP, G.GA])
def test_unsupported_guides_are_rejected(guide: CamusConfig.GuideTree):
    # CAMUS refuses a non-binary/unrooted constraint tree, so mp (majority
    # consensus -> polytomies) and ga (unrooted) can't be guides. Fail at config
    # load, not mid-run.
    assert not guide.supported
    with pytest.raises(ValidationError, match="unsupported CAMUS guide tree"):
        CamusConfig(guide_trees=[guide])


def test_dependencies_dedup_and_drop_true_tree():
    config = CamusConfig(guide_trees=[G.ASTRAL3, G.TRUE_TREE, G.ASTRAL3])
    assert CamusRunner.dependencies(config) == [TreeInferenceMethod.PCH_ASTRAL3]
