from datetime import datetime, timezone
from pathlib import Path

import polars as pl
import yaml
from typer.testing import CliRunner

from scripts.lib.inference import api
from scripts.lib.inference.inference import InferenceResult, TreeInferenceMethod, RunStatus
from scripts.py.cli import main

runner = CliRunner()


def _write_experiment(tmp_path: Path, methods: dict, paths: list[Path]) -> Path:
    """Write a spec yaml + a minimal sim registry; return the spec path."""
    for p in paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("id,feature,weight,A,B\n")
    n = len(paths)
    sim_dir = tmp_path / "simulation_data"
    sim_dir.mkdir(parents=True, exist_ok=True)
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
    ).write_csv(sim_dir / "simulated_data_registry.csv")
    spec = tmp_path / "experiment_specification.yaml"
    spec.write_text(
        yaml.safe_dump(
            {
                "experiment_folder": str(tmp_path),
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
                "methods": methods,
            }
        )
    )
    return spec


def _result() -> InferenceResult:
    return InferenceResult(
        dataset_id="d",
        tree_inference_method=TreeInferenceMethod.MP,
        config_hash="h",
        method_config_json="{}",
        point_estimate_newick="(A,B);",
        runtime_seconds=1.0,
        status=RunStatus.OK,
        ran_at=datetime.now(timezone.utc).isoformat(),
    )


def test_infer_command_invokes_api(tmp_path: Path, monkeypatch):
    calls = {}

    def fake_infer(input_csv, output_dir, method, config, *, name=None):
        calls["method"] = method
        return _result()

    monkeypatch.setattr(api, "infer", fake_infer)
    res = runner.invoke(
        main.app, ["infer", "in.csv", str(tmp_path), "--method", "mp", "--json"]
    )
    assert res.exit_code == 0, res.output
    assert calls["method"] == TreeInferenceMethod.MP
    assert '"method": "mp"' in res.output


def test_infer_requires_method(tmp_path: Path):
    res = runner.invoke(main.app, ["infer", "in.csv", str(tmp_path)])
    assert res.exit_code != 0  # --method is required


def test_experiment_inference_invokes_handler(monkeypatch):
    called = {}

    def fake_handle(cfg, *, datasets=None, method=None):
        called["datasets"] = datasets
        called["method"] = method
        return Path("out.csv")

    monkeypatch.setattr(main, "handle_inference", fake_handle)
    monkeypatch.setattr(main, "_get_experiment_config", lambda p: object())
    res = runner.invoke(main.app, ["experiment", "inference", "spec.yaml"])
    assert res.exit_code == 0, res.output
    assert called == {"datasets": None, "method": None}


def test_experiment_inference_slurm_dry_run(tmp_path: Path):
    spec = _write_experiment(
        tmp_path,
        methods={
            "mp4": {},
            "astral_3": {"is_exact": False, "bipartition_strategies": ["mp4_trees"]},
        },
        paths=[tmp_path / "sim" / "cond_a" / "d1.csv"],
    )
    res = runner.invoke(
        main.app,
        ["experiment", "inference", str(spec), "--executor", "slurm", "--dry-run"],
    )
    assert res.exit_code == 0, res.output
    # DAG printed: both methods + the compact job, with the ASTRAL3 afterok edge.
    assert "mp@cond_a" in res.output
    assert "pch_astral3@cond_a" in res.output
    assert "afterok:mp@cond_a" in res.output
    assert "afterany" in res.output
    # dry-run submits nothing but does stage the per-condition batch files.
    inf = tmp_path / "inference_data"
    assert (inf / "batches" / "cond_a.txt").exists()
    assert not (inf / "submitit").exists()


def test_experiment_inference_slurm_no_sbatch_errors(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda _name: None)
    spec = _write_experiment(
        tmp_path,
        methods={"mp4": {}},
        paths=[tmp_path / "sim" / "cond_a" / "d1.csv"],
    )
    res = runner.invoke(
        main.app, ["experiment", "inference", str(spec), "--executor", "slurm"]
    )
    assert res.exit_code != 0
    assert "sbatch" in res.output


def test_experiment_status_takes_yaml(monkeypatch, tmp_path: Path):
    seen = {}
    monkeypatch.setattr(main, "handle_status", lambda cfg: seen.setdefault("cfg", cfg))
    spec = _write_experiment(
        tmp_path, methods={"mp4": {}}, paths=[tmp_path / "sim" / "c" / "d.csv"]
    )
    res = runner.invoke(main.app, ["experiment", "status", str(spec)])
    assert res.exit_code == 0, res.output
    assert seen["cfg"].experiment_folder == tmp_path


def test_experiment_compact_takes_yaml(monkeypatch, tmp_path: Path):
    seen = {}

    def fake_compact(folder):
        seen["folder"] = folder
        return folder / "inference_registry.csv"

    monkeypatch.setattr(main.registry, "compact", fake_compact)
    spec = _write_experiment(
        tmp_path, methods={"mp4": {}}, paths=[tmp_path / "sim" / "c" / "d.csv"]
    )
    res = runner.invoke(main.app, ["experiment", "compact", str(spec)])
    assert res.exit_code == 0, res.output
    assert seen["folder"] == tmp_path
