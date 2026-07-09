from pathlib import Path

import pytest

from scripts.lib.inference.inference import (
    InferenceResult,
    RunStatus,
    TreeInferenceMethod,
)
from scripts.lib.inference.inference import TreeInferenceMethod as T
from scripts.lib.inference.registry import compact, write_result
from scripts.lib.inference.scheduler import completed_runs, topological_order


def _result(
    ran_at: str, *, dataset_id: str = "ds1", config_hash: str = "abc"
) -> InferenceResult:
    return InferenceResult(
        dataset_id=dataset_id,
        tree_inference_method=TreeInferenceMethod.MP,
        config_hash=config_hash,
        method_config_json="{}",
        point_estimate_newick="(a,b);",
        runtime_seconds=1.0,
        status=RunStatus.OK,
        ran_at=ran_at,
    )


def test_completed_runs_sees_shard_only_progress(tmp_path: Path):
    # A SLURM batch job wrote a shard; nothing compacted yet (no registry.csv).
    write_result(_result("2026-01-01T00:00:00+00:00"), tmp_path)
    done = completed_runs(tmp_path)
    assert done[("ds1",)] == {("mp", "abc")}  # visible without compaction


def test_completed_runs_unions_and_dedups_registry_and_shard(tmp_path: Path):
    # ds1 compacted into registry.csv; then ds1 (dup) + ds2 land in a new shard.
    write_result(_result("2026-01-01T00:00:00+00:00"), tmp_path)
    compact(tmp_path)  # ds1 -> registry.csv, shard cleaned
    write_result(_result("2026-01-02T00:00:00+00:00"), tmp_path)  # same key, in shard
    write_result(_result("2026-01-03T00:00:00+00:00", dataset_id="ds2"), tmp_path)
    done = completed_runs(tmp_path)
    assert done[("ds1",)] == {("mp", "abc")}  # dedups across the two sources
    assert done[("ds2",)] == {("mp", "abc")}


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
