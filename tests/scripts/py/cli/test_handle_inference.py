from datetime import datetime, timezone
from pathlib import Path

import polars as pl
import pytest

from scripts.lib.experiment import (
    ASTRAL3Config,
    ExperimentConfig,
    GAConfig,
    MethodConfig,
    MP4Config,
)
from scripts.lib.inference import api
from scripts.lib.inference.inference import (
    InferenceResult,
    TreeInferenceMethod,
    RunStatus,
)
from scripts.lib.types import Polymorphism
import scripts.py.cli.handle_inference as hi
from scripts.lib.inference.scoring import ScoreResult
from scripts.py.cli.handle_inference import (
    handle_inference,
    pipeline_config,
    select_methods,
)


def test_select_methods_mp_only():
    cfg = ExperimentConfig.model_validate(_config(Path("x")))
    assert select_methods(cfg.methods) == [TreeInferenceMethod.MP]


def test_select_methods_dependency_order():
    cfg = ExperimentConfig.model_validate(
        _config(
            Path("x"),
            methods={"mp4": {}, "gray_atkinson": {}, "astral_3": {"is_exact": True}},
        )
    )
    assert select_methods(cfg.methods) == [
        TreeInferenceMethod.MP,
        TreeInferenceMethod.GA,
        TreeInferenceMethod.PCH_ASTRAL3,
    ]


def test_select_methods_respects_enabled():
    cfg = ExperimentConfig.model_validate(
        _config(
            Path("x"), methods={"gray_atkinson": {}, "astral_3": {"is_exact": True}}
        )
    )
    assert select_methods(cfg.methods) == [
        TreeInferenceMethod.GA,
        TreeInferenceMethod.PCH_ASTRAL3,
    ]


def test_select_methods_heuristic_astral3_requires_mp4_ga():
    cfg = ExperimentConfig.model_validate(
        _config(Path("x"), methods={"astral_3": {"is_exact": False}})
    )
    with pytest.raises(ValueError, match="requires.*mp4"):
        select_methods(cfg.methods)


def test_select_methods_default_strategies_missing_ga_raises():
    cfg = ExperimentConfig.model_validate(
        _config(Path("x"), methods={"mp4": {}, "astral_3": {"is_exact": False}})
    )
    with pytest.raises(ValueError, match="gray_atkinson"):
        select_methods(cfg.methods)


def test_select_methods_mp4_strategy_only_no_ga_ok():
    # strategies=[mp4_trees] → GA not required; mp4 alone satisfies it.
    cfg = ExperimentConfig.model_validate(
        _config(
            Path("x"),
            methods={
                "mp4": {},
                "astral_3": {
                    "is_exact": False,
                    "bipartition_strategies": ["mp4_trees"],
                },
            },
        )
    )
    assert select_methods(cfg.methods) == [
        TreeInferenceMethod.MP,
        TreeInferenceMethod.PCH_ASTRAL3,
    ]


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


def test_handle_inference_writes_registry(tmp_path: Path, monkeypatch):
    sim_dir = tmp_path / "simulation_data" / "simulated_data"
    cond_dir = sim_dir / "high_0.1_4_320"
    cond_dir.mkdir(parents=True)
    dataset = cond_dir / "sim_0_1_1.csv"
    dataset.write_text("id,feature,weight,A,B\n")

    base_tree = tmp_path / "base.txt"
    base_tree.write_text("(A,B);\n")
    pl.DataFrame(
        {
            "horizontal_edges": [0],
            "model_tree": [1],
            "path": [str(base_tree)],
        }
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

    def fake_infer(input_csv, output_dir, method, config, *, name=None):
        return InferenceResult(
            dataset_id=input_csv.stem,
            tree_inference_method=method,
            config_hash="hash",
            method_config_json="{}",
            point_estimate_newick="(A,B);",
            runtime_seconds=1.0,
            status=RunStatus.OK,
            ran_at=datetime.now(timezone.utc).isoformat(),
        )

    monkeypatch.setattr(api, "infer", fake_infer)
    monkeypatch.setattr(hi, "score", lambda est, ref: ScoreResult(0.25, 0.5))

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
    assert r["fn_rate"] == 0.25
    assert r["fp_rate"] == 0.5
    assert Polymorphism(r["poly_level"]) is Polymorphism.HIGH


def test_handle_inference_runs_methods_in_order(tmp_path: Path, monkeypatch):
    sim_dir = tmp_path / "simulation_data" / "simulated_data"
    cond_dir = sim_dir / "high_0.1_4_320"
    cond_dir.mkdir(parents=True)
    dataset = cond_dir / "sim_0_1_1.csv"
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

    calls: list[TreeInferenceMethod] = []

    def fake_infer(input_csv, output_dir, method, config, *, name=None):
        calls.append(method)
        return InferenceResult(
            dataset_id=input_csv.stem,
            tree_inference_method=method,
            config_hash="hash",
            method_config_json="{}",
            point_estimate_newick="(A,B);",
            runtime_seconds=1.0,
            status=RunStatus.OK,
            ran_at=datetime.now(timezone.utc).isoformat(),
        )

    monkeypatch.setattr(api, "infer", fake_infer)
    monkeypatch.setattr(hi, "score", lambda est, ref: ScoreResult(0.25, 0.5))

    cfg = ExperimentConfig.model_validate(
        _config(
            tmp_path,
            methods={"mp4": {}, "gray_atkinson": {}, "astral_3": {"is_exact": True}},
        )
    )
    out = handle_inference(cfg)

    assert calls == [
        TreeInferenceMethod.MP,
        TreeInferenceMethod.GA,
        TreeInferenceMethod.PCH_ASTRAL3,
    ]
    df = pl.read_csv(out)
    assert sorted(df["method"].to_list()) == ["ga", "mp", "pch_astral3"]


def test_handle_inference_astral3_failed_when_ga_fails(tmp_path: Path, monkeypatch):
    sim_dir = tmp_path / "simulation_data" / "simulated_data"
    cond_dir = sim_dir / "high_0.1_4_320"
    cond_dir.mkdir(parents=True)
    dataset = cond_dir / "sim_0_1_1.csv"
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

    calls: list[TreeInferenceMethod] = []

    def fake_infer(input_csv, output_dir, method, config, *, name=None):
        calls.append(method)
        status = (
            RunStatus.FAILED if method is TreeInferenceMethod.GA else RunStatus.OK
        )
        return InferenceResult(
            dataset_id=input_csv.stem,
            tree_inference_method=method,
            config_hash="hash",
            method_config_json="{}",
            point_estimate_newick="(A,B);" if status is RunStatus.OK else "",
            runtime_seconds=1.0,
            status=status,
            ran_at=datetime.now(timezone.utc).isoformat(),
        )

    monkeypatch.setattr(api, "infer", fake_infer)
    monkeypatch.setattr(hi, "score", lambda est, ref: ScoreResult(0.25, 0.5))

    cfg = ExperimentConfig.model_validate(
        _config(
            tmp_path,
            methods={"mp4": {}, "gray_atkinson": {}, "astral_3": {"is_exact": False}},
        )
    )
    out = handle_inference(cfg)

    # Heuristic ASTRAL3 gated on in-memory GA success → never invoked.
    assert TreeInferenceMethod.PCH_ASTRAL3 not in calls
    df = pl.read_csv(out)
    a3 = df.filter(pl.col("method") == "pch_astral3").row(0, named=True)
    assert a3["status"] == "failed"
    # failed_result fills real fields: non-empty config_hash (dedupe key) + a log.
    assert a3["config_hash"]
    assert a3["log_path"]


def test_handle_inference_astral3_runs_when_upstream_ok(tmp_path: Path, monkeypatch):
    sim_dir = tmp_path / "simulation_data" / "simulated_data"
    cond_dir = sim_dir / "high_0.1_4_320"
    cond_dir.mkdir(parents=True)
    dataset = cond_dir / "sim_0_1_1.csv"
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

    calls: list[TreeInferenceMethod] = []

    def fake_infer(input_csv, output_dir, method, config, *, name=None):
        calls.append(method)
        return InferenceResult(
            dataset_id=input_csv.stem,
            tree_inference_method=method,
            config_hash="hash",
            method_config_json="{}",
            point_estimate_newick="(A,B);",
            runtime_seconds=1.0,
            status=RunStatus.OK,
            ran_at=datetime.now(timezone.utc).isoformat(),
        )

    monkeypatch.setattr(api, "infer", fake_infer)
    monkeypatch.setattr(hi, "score", lambda est, ref: ScoreResult(0.25, 0.5))

    cfg = ExperimentConfig.model_validate(
        _config(
            tmp_path,
            methods={"mp4": {}, "gray_atkinson": {}, "astral_3": {"is_exact": False}},
        )
    )
    handle_inference(cfg)

    # MP4 + GA both OK → heuristic gate passes → ASTRAL3 IS invoked.
    assert TreeInferenceMethod.PCH_ASTRAL3 in calls


def test_astral3_upstream_failed_only_gates_required_methods():
    # strategies=[mp4_trees] → GA failure is irrelevant; only MP4 matters.
    methods = MethodConfig(
        mp4=MP4Config(),
        astral_3=ASTRAL3Config(is_exact=False, bipartition_strategies=["mp4_trees"]),
    )
    statuses = {
        TreeInferenceMethod.MP: RunStatus.OK,
        TreeInferenceMethod.GA: RunStatus.FAILED,
    }
    assert not hi._astral3_upstream_failed(
        methods, TreeInferenceMethod.PCH_ASTRAL3, statuses
    )
    statuses[TreeInferenceMethod.MP] = RunStatus.FAILED
    assert hi._astral3_upstream_failed(
        methods, TreeInferenceMethod.PCH_ASTRAL3, statuses
    )


def test_pipeline_config_maps_method_to_config_type():
    methods = MethodConfig(
        mp4=MP4Config(),
        gray_atkinson=GAConfig(),
        astral_3=ASTRAL3Config(is_exact=True),
    )
    assert isinstance(pipeline_config(methods, TreeInferenceMethod.MP), MP4Config)
    assert isinstance(pipeline_config(methods, TreeInferenceMethod.GA), GAConfig)
    assert isinstance(
        pipeline_config(methods, TreeInferenceMethod.PCH_ASTRAL3), ASTRAL3Config
    )
