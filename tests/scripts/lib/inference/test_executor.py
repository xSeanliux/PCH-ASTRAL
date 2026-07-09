from pathlib import Path

from scripts.lib.experiment import ExperimentConfig
from scripts.lib.inference.executor import JobSpec, SlurmExecutor


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


def test_plan_one_job_per_condition_method(tmp_path: Path):
    plan = SlurmExecutor(_config(tmp_path))._plan(_rows(), astral_mem_gb=None)
    batch = _batch(plan)
    # 2 conditions × 3 methods.
    assert {(s.condition, s.method) for s in batch} == {
        (c, m)
        for c in ("netA", "netB")
        for m in ("mp", "ga", "pch_astral3")
    }
    assert len(batch) == 6


def test_astral3_deps_are_same_condition(tmp_path: Path):
    plan = SlurmExecutor(_config(tmp_path))._plan(_rows(), astral_mem_gb=None)
    a3 = next(s for s in plan if s.method == "pch_astral3" and s.condition == "netA")
    # MP4 AND GA of netA — never netB.
    assert set(a3.dep_labels) == {"mp@netA", "ga@netA"}


def test_tiers_and_astral_mem(tmp_path: Path):
    plan = SlurmExecutor(_config(tmp_path))._plan(_rows(), astral_mem_gb=128)
    a3 = next(s for s in plan if s.method == "pch_astral3")
    mp = next(s for s in plan if s.method == "mp")
    assert a3.tier == "heavy" and a3.mem_gb == 128  # override honored
    assert mp.tier == "light" and mp.mem_gb < a3.mem_gb


def test_compact_depends_on_all_methods(tmp_path: Path):
    plan = SlurmExecutor(_config(tmp_path))._plan(_rows(), astral_mem_gb=None)
    compact = plan[-1]
    assert compact.kind == "compact"
    assert compact.dep_mode == "afterany"
    assert set(compact.dep_labels) == {s.label for s in _batch(plan)}


def test_default_astral_mem(tmp_path: Path):
    plan = SlurmExecutor(_config(tmp_path))._plan(_rows(), astral_mem_gb=None)
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
