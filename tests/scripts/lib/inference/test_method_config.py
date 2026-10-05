from scripts.lib.experiment import ASTRAL3Config, MP4Config, WeightedTreeQMCConfig
from scripts.lib.model.methods import TreeInferenceMethod
from scripts.lib.model.strategies import NormalisationStrategy
from scripts.lib.inference.method_config import hash_config, resolve_config


def test_resolve_config_defaults() -> None:
    cfg = resolve_config(TreeInferenceMethod.MP, None)
    assert isinstance(cfg, MP4Config)


def test_config_hash_stable_and_distinct() -> None:
    a = resolve_config(TreeInferenceMethod.MP, None)
    assert hash_config(a) == hash_config(a)

    b = WeightedTreeQMCConfig(normalisation_strategy=NormalisationStrategy.N2)
    assert hash_config(a) != hash_config(b)


def test_tree_method_hashes_are_pinned() -> None:
    # Changing these orphans every registry row (resume key); change deliberately.
    assert (
        hash_config(MP4Config())
        == "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
    )
    assert (
        hash_config(ASTRAL3Config(is_exact=False))
        == "e5f6e68cda9cad3362def4d2211671073cc6925d74e76fb6c205ebcb81265d87"
    )
