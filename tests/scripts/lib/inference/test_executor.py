import os
from collections.abc import Callable
from pathlib import Path

import pytest

from scripts.lib.experiment import ExperimentConfig
from scripts.lib.inference import executor as executor_mod
from scripts.lib.inference.executor import JobSpec, Param, SlurmExecutor


def _config(folder: Path) -> ExperimentConfig:
    return ExperimentConfig.model_validate(
        {
            "experiment_folder": str(folder),
            "simulation": {
                "n_horizontal_edges": [0],
                "n_trees": 1,
                "n_replicas": 1,
                "n_taxa": 4,
                "base_config_dir": "configs",
                "base_trees_file": "trees.txt",
                "base_networks_dir": "nets",
                "simulation_params": [],
            },
            "methods": {
                "mp4": {},
                "gray_atkinson": {},
                "astral_3": {"is_exact": False},  # heuristic ⇒ deps on MP4+GA
            },
        }
    )


def _rows() -> list[dict[str, str]]:
    # 2 conditions × 2 datasets each; condition = parent-dir name.
    return [
        {"path": "exp/simulation_data/netA/d1.csv"},
        {"path": "exp/simulation_data/netA/d2.csv"},
        {"path": "exp/simulation_data/netB/d1.csv"},
        {"path": "exp/simulation_data/netB/d2.csv"},
    ]


def _batch(specs: list[JobSpec]) -> list[JobSpec]:
    return [s for s in specs if s.kind == "batch"]


def _plan(tmp_path: Path, **kw) -> list[JobSpec]:
    ex = SlurmExecutor(_config(tmp_path))
    return ex._plan(ex._group_conditions(_rows()), **kw)


def test_plan_one_job_per_condition_method(tmp_path: Path):
    plan = _plan(tmp_path, astral_mem_gb=None)
    batch = _batch(plan)
    # 2 conditions × 3 methods.
    assert {(s.condition, s.method) for s in batch} == {
        (c, m)
        for c in ("netA", "netB")
        for m in ("mp", "ga", "pch_astral3")
    }
    assert len(batch) == 6


def test_astral3_deps_are_same_condition(tmp_path: Path):
    plan = _plan(tmp_path, astral_mem_gb=None)
    a3 = next(s for s in plan if s.method == "pch_astral3" and s.condition == "netA")
    # MP4 AND GA of netA — never netB.
    assert set(a3.dep_labels) == {"mp@netA", "ga@netA"}


def test_tiers_and_astral_mem(tmp_path: Path):
    plan = _plan(tmp_path, astral_mem_gb=128)
    a3 = next(s for s in plan if s.method == "pch_astral3")
    mp = next(s for s in plan if s.method == "mp")
    assert a3.tier == "heavy" and a3.mem_gb == 128  # override honored
    assert mp.tier == "light" and mp.mem_gb < a3.mem_gb


def test_compact_depends_on_all_methods(tmp_path: Path):
    plan = _plan(tmp_path, astral_mem_gb=None)
    compact = plan[-1]
    assert compact.kind == "compact"
    assert compact.dep_mode == "afterany"
    assert set(compact.dep_labels) == {s.label for s in _batch(plan)}


def test_default_astral_mem(tmp_path: Path):
    plan = _plan(tmp_path, astral_mem_gb=None)
    a3 = next(s for s in plan if s.method == "pch_astral3")
    assert a3.mem_gb == 64  # heavy default when no override


def test_dry_run_writes_batches_without_submitting(tmp_path: Path):
    ex = SlurmExecutor(_config(tmp_path))
    plan = ex.fan_out(_rows(), dry_run=True)

    # Returned the plan, not submitit jobs.
    assert all(isinstance(s, JobSpec) for s in plan)

    batches = tmp_path / "inference_data" / "batches"
    assert (batches / "netA.txt").read_text().splitlines() == [
        "exp/simulation_data/netA/d1.csv",
        "exp/simulation_data/netA/d2.csv",
    ]
    assert (batches / "netB.txt").read_text().splitlines() == [
        "exp/simulation_data/netB/d1.csv",
        "exp/simulation_data/netB/d2.csv",
    ]
    # No submission side effects.
    assert not (tmp_path / "inference_data" / "submitit").exists()


def test_method_restricts_plan(tmp_path: Path):
    plan = _plan(tmp_path, method="pch_astral3", astral_mem_gb=None)
    batch = _batch(plan)
    assert {s.method for s in batch} == {"pch_astral3"}
    # Deps (MP4/GA) not in this run ⇒ no edges; they ran in a prior invocation.
    assert all(s.dep_labels == () for s in batch)


def test_method_not_enabled_errors(tmp_path: Path):
    with pytest.raises(ValueError, match="not enabled"):
        _plan(tmp_path, method="not_a_method", astral_mem_gb=None)


def test_datasets_filter_restricts_conditions(tmp_path: Path):
    keep = tmp_path / "keep.txt"
    keep.write_text("exp/simulation_data/netA/d1.csv\n")
    plan = SlurmExecutor(_config(tmp_path)).fan_out(
        _rows(), datasets=keep, dry_run=True
    )
    conds = {
        s.condition for s in plan if isinstance(s, JobSpec) and s.kind == "batch"
    }
    assert conds == {"netA"}


def test_condition_name_collision_errors(tmp_path: Path):
    ex = SlurmExecutor(_config(tmp_path))
    rows = [{"path": "a/net/d1.csv"}, {"path": "b/net/d2.csv"}]  # same parent name
    with pytest.raises(ValueError, match="collides"):
        ex._group_conditions(rows)


class _FakeJob:
    def __init__(self, jid: str) -> None:
        self.job_id = jid


class _FakeExecutor:
    """Records the params update for each submitted job (no sbatch needed)."""

    def __init__(self, folder: Path) -> None:
        self._n = 0
        self._last: dict[str, Param] = {}
        self.captured: list[dict[str, Param]] = []

    def update_parameters(self, **kw: Param) -> None:
        self._last = kw

    def submit(self, fn: Callable[..., None], *args: str) -> _FakeJob:
        self.captured.append(self._last)
        self._n += 1
        return _FakeJob(str(self._n))


def test_submit_pins_chdir_and_merges_dependency(tmp_path: Path, monkeypatch):
    fx = _FakeExecutor(tmp_path)
    monkeypatch.setattr(executor_mod, "AutoExecutor", lambda folder: fx)
    SlurmExecutor(_config(tmp_path)).fan_out(_rows(), dry_run=False)

    assert fx.captured, "no jobs submitted"
    cwd = os.getcwd()
    extras: list[dict[str, str]] = []
    for params in fx.captured:
        extra = params["slurm_additional_parameters"]
        assert isinstance(extra, dict)  # narrow Param union
        # Every job pins the submission cwd so relative paths resolve on the node.
        assert extra["chdir"] == cwd
        extras.append(extra)
    # chdir MERGES with the dependency edge (ASTRAL3 depends on MP4/GA).
    dep_extras = [e for e in extras if "dependency" in e]
    assert dep_extras and all(e["chdir"] == cwd for e in dep_extras)
