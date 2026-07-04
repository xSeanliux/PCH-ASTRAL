import pytest

from scripts.lib.inference.inference import TreeInferenceMethod as T
from scripts.lib.inference.scheduler import topological_order


def test_topo_orders_deps_before_dependents():
    order = topological_order(
        [T.PCH_ASTRAL3, T.MP, T.GA],
        {T.PCH_ASTRAL3: [T.MP, T.GA], T.MP: [], T.GA: []},
    )
    assert order.index(T.MP) < order.index(T.PCH_ASTRAL3)
    assert order.index(T.GA) < order.index(T.PCH_ASTRAL3)


def test_topo_ignores_deps_not_in_the_run():
    # ASTRAL3 alone (MP4/GA run separately) — the missing deps don't hang/cycle.
    assert topological_order(
        [T.PCH_ASTRAL3], {T.PCH_ASTRAL3: [T.MP, T.GA]}
    ) == [T.PCH_ASTRAL3]


def test_topo_stable_by_input_order():
    assert topological_order([T.MP, T.GA], {T.MP: [], T.GA: []}) == [T.MP, T.GA]


def test_topo_cycle_raises():
    with pytest.raises(ValueError, match="cycle"):
        topological_order([T.MP, T.GA], {T.MP: [T.GA], T.GA: [T.MP]})
