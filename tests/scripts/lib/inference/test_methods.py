from scripts.lib.experiment import MP4Config, WeightedTreeQMCConfig
from scripts.lib.inference.inference import TreeInferenceMethod
from scripts.lib.inference.methods import config_hash, resolve_config


def test_resolve_config_defaults() -> None:
    cfg = resolve_config(TreeInferenceMethod.MP, None)
    assert isinstance(cfg, MP4Config)


def test_config_hash_stable_and_distinct() -> None:
    a = resolve_config(TreeInferenceMethod.MP, None)
    assert config_hash(a) == config_hash(a)

    b = WeightedTreeQMCConfig(
        normalisation_strategy=WeightedTreeQMCConfig.NormalisationStrategy.N2
    )
    assert config_hash(a) != config_hash(b)
