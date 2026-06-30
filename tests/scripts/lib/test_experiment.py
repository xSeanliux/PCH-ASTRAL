import pytest

from scripts.lib.experiment import ASTRAL3Config

S = ASTRAL3Config.BipartitionStrategy


def test_effective_strategies_default_is_mp4_ga():
    assert ASTRAL3Config(is_exact=False).effective_strategies == [
        S.MP4_TREES,
        S.GA_TREES,
    ]


def test_effective_strategies_passthrough():
    cfg = ASTRAL3Config(is_exact=False, bipartition_strategies=[S.GA_TREES])
    assert cfg.effective_strategies == [S.GA_TREES]


def test_effective_strategies_binary_character_not_implemented():
    cfg = ASTRAL3Config(is_exact=False, bipartition_strategies=[S.BINARY_CHARACTER])
    with pytest.raises(NotImplementedError):
        cfg.effective_strategies
