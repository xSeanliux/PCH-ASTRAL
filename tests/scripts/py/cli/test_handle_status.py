from pathlib import Path

import polars as pl

from scripts.lib.experiment import ExperimentConfig
from scripts.lib.inference import registry
from scripts.lib.inference.inference import TreeInferenceMethod
from scripts.lib.inference.scheduler import DatasetKey
from scripts.py.cli.handle_status import compute_status, handle_status


# ── fixtures ──────────────────────────────────────────────────────────────────

def _config(folder: Path, methods: dict | None = None) -> dict:
    return {
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
        "methods": methods if methods is not None else {"mp4": {}},
    }


def _write_sim_registry(tmp_path: Path, paths: list[Path]) -> Path:
    """Write a minimal simulated_data_registry.csv with the given dataset paths."""
    n = len(paths)
    sim_dir = tmp_path / "simulation_data"
    sim_dir.mkdir(parents=True, exist_ok=True)
    out = sim_dir / "simulated_data_registry.csv"
    pl.DataFrame(
        {
            "poly_level": ["high"] * n,
            "character_count": [320] * n,
            "min_tree_height": [4] * n,
            "homoplasy_factor": [0.1] * n,
            "horizontal_edges": [0] * n,
            "model_tree": [1] * n,
            "replica": list(range(1, n + 1)),
            "path": [str(p) for p in paths],
        }
    ).write_csv(out)
    return out


def _done_for(
    paths: list[Path], methods: list[str], config_hash: str = "abc"
) -> dict[DatasetKey, set[tuple[str, str]]]:
    return {
        (registry.canonical_path(str(p)),): {(m, config_hash) for m in methods}
        for p in paths
    }


# ── compute_status unit tests ─────────────────────────────────────────────────

def _rows(paths: list[Path]) -> list[dict[str, str | int | float]]:
    return [
        {
            "poly_level": "high",
            "character_count": 320,
            "min_tree_height": 4,
            "homoplasy_factor": 0.1,
            "horizontal_edges": 0,
            "model_tree": 1,
            "replica": i + 1,
            "path": str(p),
        }
        for i, p in enumerate(paths)
    ]


def test_compute_status_none_done(tmp_path: Path) -> None:
    cond_a = tmp_path / "cond_a"
    cond_b = tmp_path / "cond_b"
    paths_a = [cond_a / "sim_1.csv", cond_a / "sim_2.csv"]
    paths_b = [cond_b / "sim_3.csv"]

    methods = [TreeInferenceMethod.MP]
    counts, missing = compute_status(_rows(paths_a + paths_b), methods, done={})

    assert counts == {("cond_a", "mp"): (0, 2), ("cond_b", "mp"): (0, 1)}
    assert set(missing[("cond_a", "mp")]) == {"sim_1", "sim_2"}
    assert missing[("cond_b", "mp")] == ["sim_3"]


def test_compute_status_partial_done(tmp_path: Path) -> None:
    cond_a = tmp_path / "cond_a"
    paths = [cond_a / "sim_1.csv", cond_a / "sim_2.csv", cond_a / "sim_3.csv"]
    methods = [TreeInferenceMethod.MP]

    # Only sim_1 done for mp
    done = _done_for([paths[0]], ["mp"])
    counts, missing = compute_status(_rows(paths), methods, done=done)

    assert counts[("cond_a", "mp")] == (1, 3)
    assert set(missing[("cond_a", "mp")]) == {"sim_2", "sim_3"}


def test_compute_status_all_done(tmp_path: Path) -> None:
    cond = tmp_path / "my_cond"
    paths = [cond / "sim_1.csv", cond / "sim_2.csv"]
    methods = [TreeInferenceMethod.MP, TreeInferenceMethod.GA]

    done = _done_for(paths, ["mp", "ga"])
    counts, missing = compute_status(_rows(paths), methods, done=done)

    assert counts[("my_cond", "mp")] == (2, 2)
    assert counts[("my_cond", "ga")] == (2, 2)
    # No missing entries for fully-done keys
    assert missing.get(("my_cond", "mp"), []) == []
    assert missing.get(("my_cond", "ga"), []) == []


def test_compute_status_two_conditions(tmp_path: Path) -> None:
    cond_a = tmp_path / "cond_a"
    cond_b = tmp_path / "cond_b"
    pa = [cond_a / "d1.csv", cond_a / "d2.csv"]
    pb = [cond_b / "d3.csv"]
    methods = [TreeInferenceMethod.MP]

    # cond_a: d1 done, d2 missing; cond_b: d3 done
    done = _done_for([pa[0], pb[0]], ["mp"])
    counts, missing = compute_status(_rows(pa + pb), methods, done=done)

    assert counts[("cond_a", "mp")] == (1, 2)
    assert counts[("cond_b", "mp")] == (1, 1)
    assert missing[("cond_a", "mp")] == ["d2"]
    assert ("cond_b", "mp") not in missing or missing[("cond_b", "mp")] == []


def test_compute_status_method_partial_across_methods(tmp_path: Path) -> None:
    cond = tmp_path / "cond"
    paths = [cond / "sim_1.csv"]
    methods = [TreeInferenceMethod.MP, TreeInferenceMethod.GA]

    # mp done, ga not
    done = _done_for(paths, ["mp"])
    counts, missing = compute_status(_rows(paths), methods, done=done)

    assert counts[("cond", "mp")] == (1, 1)
    assert counts[("cond", "ga")] == (0, 1)
    assert missing[("cond", "ga")] == ["sim_1"]
    assert missing.get(("cond", "mp"), []) == []


# ── handle_status integration smoke tests ─────────────────────────────────────

def test_handle_status_no_registry(tmp_path: Path) -> None:
    cfg = ExperimentConfig.model_validate(_config(tmp_path))
    # Must not raise; sim registry absent → early return
    handle_status(cfg)


def test_handle_status_smoke(tmp_path: Path) -> None:
    cond_a = tmp_path / "simulation_data" / "simulated_data" / "cond_a"
    cond_b = tmp_path / "simulation_data" / "simulated_data" / "cond_b"
    cond_a.mkdir(parents=True)
    cond_b.mkdir(parents=True)

    d1, d2 = cond_a / "sim_1.csv", cond_b / "sim_2.csv"
    for d in (d1, d2):
        d.write_text("id,feature,weight,A,B\n")

    _write_sim_registry(tmp_path, [d1, d2])

    # No inference data → all missing; should print without crashing
    cfg = ExperimentConfig.model_validate(_config(tmp_path, methods={"mp4": {}, "gray_atkinson": {}}))
    handle_status(cfg)  # smoke: no exception


def test_handle_status_counts_match_compute(tmp_path: Path) -> None:
    """Integration: handle_status driven by a real (partial) inference shard."""
    from scripts.lib.inference import registry as reg
    import json
    from datetime import datetime, timezone

    cond = tmp_path / "simulation_data" / "simulated_data" / "cond_x"
    cond.mkdir(parents=True)
    d1, d2 = cond / "sim_1.csv", cond / "sim_2.csv"
    d1.write_text("id,feature,weight,A,B\n")
    d2.write_text("id,feature,weight,A,B\n")

    _write_sim_registry(tmp_path, [d1, d2])

    # Write a shard row: only d1/mp done
    shards = tmp_path / "inference_data" / "shards"
    shards.mkdir(parents=True)
    row = {
        "dataset_id": reg.canonical_path(str(d1)),
        "method": "mp",
        "config_hash": "abc",
        "method_config_json": "{}",
        "runtime_seconds": 1.0,
        "point_estimate_newick": "(A,B);",
        "tree_set_path": "",
        "consensus_method": "",
        "status": "ok",
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "log_path": "",
    }
    (shards / "local-1.jsonl").write_text(json.dumps(row) + "\n")

    cfg = ExperimentConfig.model_validate(_config(tmp_path, methods={"mp4": {}}))
    methods = [TreeInferenceMethod.MP]
    done = __import__(
        "scripts.lib.inference.scheduler", fromlist=["completed_runs"]
    ).completed_runs(tmp_path)

    rows_data = list(
        pl.read_csv(
            tmp_path / "simulation_data" / "simulated_data_registry.csv",
            schema=__import__(
                "scripts.py.cli.schemata", fromlist=["SIMULATED_DATA_REGISTRY_SCHEMA"]
            ).SIMULATED_DATA_REGISTRY_SCHEMA,
        ).iter_rows(named=True)
    )
    counts, missing = compute_status(rows_data, methods, done)

    assert counts[("cond_x", "mp")] == (1, 2)
    assert missing[("cond_x", "mp")] == ["sim_2"]

    # Smoke: full handler runs without error
    handle_status(cfg)
