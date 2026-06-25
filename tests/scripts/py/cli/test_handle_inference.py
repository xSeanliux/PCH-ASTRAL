from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from scripts.lib.experiment import ExperimentConfig
from scripts.lib.inference import api
from scripts.lib.inference.inference import InferenceResult, TreeInferenceMethod
from scripts.lib.types import Polymorphism
from scripts.py.cli.handle_inference import handle_inference, select_methods


def test_select_methods_mp_only():
    cfg = ExperimentConfig.model_validate(_config(Path("x")))
    assert select_methods(cfg.methods) == [TreeInferenceMethod.MP]


def _config(folder: Path) -> dict:
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
        "methods": {"mp4": {}},
    }


def test_handle_inference_writes_registry(tmp_path: Path, monkeypatch):
    sim_dir = tmp_path / "simulation_data" / "simulated_data"
    cond_dir = sim_dir / "high_0.1_4_320"
    cond_dir.mkdir(parents=True)
    dataset = cond_dir / "sim_0_1_1.csv"
    dataset.write_text("id,feature,weight,A,B\n")

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

    def fake_infer(input_csv, output_dir, method, config, *, name=None):
        return InferenceResult(
            dataset_id=input_csv.stem,
            tree_inference_method=method,
            config_hash="hash",
            method_config_json="{}",
            point_estimate_newick="(A,B);",
            runtime_seconds=1.0,
            status="ok",
            ran_at=datetime.now(timezone.utc).isoformat(),
        )

    monkeypatch.setattr(api, "infer", fake_infer)

    cfg = ExperimentConfig.model_validate(_config(tmp_path))
    out = handle_inference(cfg)

    assert out == tmp_path / "inference_data" / "inference_registry.csv"
    df = pl.read_csv(out)
    assert df.height == 1
    r = df.row(0, named=True)
    assert r["method"] == "mp"
    assert r["poly_level"] == "high"
    assert r["character_count"] == 320
    assert r["model_tree"] == 1
    assert r["replica"] == 1
    assert Polymorphism(r["poly_level"]) is Polymorphism.HIGH
