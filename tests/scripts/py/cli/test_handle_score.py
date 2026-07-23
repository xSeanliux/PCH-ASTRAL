from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from scripts.lib.experiment import ExperimentConfig
from scripts.lib.inference import api
from scripts.lib.inference.inference import InferenceResult, RunStatus
from scripts.lib.inference.scoring import ScoreResult
import scripts.py.cli.handle_score as hs
from scripts.py.cli.handle_inference import handle_inference
from scripts.py.cli.handle_score import handle_score

from tests.scripts.py.cli.test_handle_inference import _config


def _setup(tmp_path: Path) -> ExperimentConfig:
    sim_dir = tmp_path / "simulation_data" / "simulated_data" / "high_0.1_4_320"
    sim_dir.mkdir(parents=True)
    dataset = sim_dir / "sim_0_1_1.csv"
    dataset.write_text("id,feature,weight,A,B\n")
    base_tree = tmp_path / "base.txt"
    base_tree.write_text("(A,B);\n")
    pl.DataFrame(
        {"horizontal_edges": [0], "model_tree": [1], "path": [str(base_tree)]}
    ).write_csv(tmp_path / "simulation_data" / "model_graph_registry.csv")
    pl.DataFrame(
        {
            "poly_level": ["high"],
            "character_count": [320],
            "min_tree_height": [4],
            "homoplasy_factor": [0.1],
            "horizontal_edges": [0],
            "model_tree": [1],
            "replica": [1],
            "path": [str(dataset)],
        }
    ).write_csv(tmp_path / "simulation_data" / "simulated_data_registry.csv")
    return ExperimentConfig.model_validate(_config(tmp_path, methods={"mp4": {}}))


def test_handle_score_writes_fn_fp(tmp_path: Path, monkeypatch):
    cfg = _setup(tmp_path)

    def fake_infer(input_csv, output_dir, method, config, *, name=None):
        return InferenceResult(
            dataset_id=str(input_csv),
            tree_inference_method=method,
            config_hash="hash",
            method_config_json="{}",
            point_estimate_newick="(A,B);",
            runtime_seconds=1.0,
            status=RunStatus.OK,
            ran_at=datetime.now(timezone.utc).isoformat(),
        )

    monkeypatch.setattr(api, "infer", fake_infer)
    handle_inference(cfg)

    monkeypatch.setattr(hs, "score", lambda est, ref: ScoreResult(0.25, 0.5))
    out = handle_score(cfg)

    df = pl.read_csv(out)
    assert df.height == 1
    r = df.row(0, named=True)
    assert r["method"] == "mp"
    assert r["config_hash"] == "hash"
    assert r["fn_rate"] == 0.25
    assert r["fp_rate"] == 0.5
    assert r["dataset_id"] == str(
        tmp_path / "simulation_data" / "simulated_data" / "high_0.1_4_320" / "sim_0_1_1.csv"
    )


def test_handle_score_dedups_duplicate_sim_rows(tmp_path: Path, monkeypatch):
    # A duplicate sim-registry `path` row fans the inf⨝sim join out; score the
    # (dataset, method, config_hash) key once, not per duplicate.
    cfg = _setup(tmp_path)
    sim_csv = tmp_path / "simulation_data" / "simulated_data_registry.csv"
    sim = pl.read_csv(sim_csv)
    pl.concat([sim, sim]).write_csv(sim_csv)  # duplicate every row

    def fake_infer(input_csv, output_dir, method, config, *, name=None):
        return InferenceResult(
            dataset_id=str(input_csv),
            tree_inference_method=method,
            config_hash="hash",
            method_config_json="{}",
            point_estimate_newick="(A,B);",
            runtime_seconds=1.0,
            status=RunStatus.OK,
            ran_at=datetime.now(timezone.utc).isoformat(),
        )

    monkeypatch.setattr(api, "infer", fake_infer)
    handle_inference(cfg)

    calls: list = []
    monkeypatch.setattr(
        hs, "score", lambda est, ref: calls.append(1) or ScoreResult(0.25, 0.5)
    )
    out = handle_score(cfg)

    assert len(calls) == 1  # scored once despite the duplicate sim row
    assert pl.read_csv(out).height == 1  # one score row, not one per duplicate


def test_handle_score_incremental(tmp_path: Path, monkeypatch):
    # Re-running score does NOT re-score already-scored entries.
    cfg = _setup(tmp_path)

    def fake_infer(input_csv, output_dir, method, config, *, name=None):
        return InferenceResult(
            dataset_id=str(input_csv),
            tree_inference_method=method,
            config_hash="hash",
            method_config_json="{}",
            point_estimate_newick="(A,B);",
            runtime_seconds=1.0,
            status=RunStatus.OK,
            ran_at=datetime.now(timezone.utc).isoformat(),
        )

    monkeypatch.setattr(api, "infer", fake_infer)
    handle_inference(cfg)

    calls: list = []
    monkeypatch.setattr(
        hs, "score", lambda est, ref: calls.append(1) or ScoreResult(0.25, 0.5)
    )
    handle_score(cfg)  # scores the one entry
    handle_score(cfg)  # already scored → nothing new

    assert len(calls) == 1  # scored once, not twice
    assert pl.read_csv(tmp_path / "inference_data" / "scores.csv").height == 1
