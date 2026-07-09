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
from scripts.lib.inference.method_config import config_for, config_hash
from scripts.py.cli.handle_inference import handle_inference, select_methods


def test_select_methods_mp_only():
    cfg = ExperimentConfig.model_validate(_config(Path("x")))
    assert select_methods(cfg.methods) == [TreeInferenceMethod.MP]


def test_select_methods_fixed_order():
    cfg = ExperimentConfig.model_validate(
        _config(
            Path("x"),
            methods={"mp4": {}, "gray_atkinson": {}, "astral_3": {"is_exact": True}},
        )
    )
    # RUNNERS order: MP4, GA, ASTRAL3 — so ASTRAL3 has its inputs in a combined run.
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


def test_select_methods_astral3_only_ok():
    # ASTRAL3 alone is allowed — MP4/GA may be a separate prior run. No co-requisite.
    cfg = ExperimentConfig.model_validate(
        _config(Path("x"), methods={"astral_3": {"is_exact": False}})
    )
    assert select_methods(cfg.methods) == [TreeInferenceMethod.PCH_ASTRAL3]


def test_config_for_matches_by_type():
    methods = MethodConfig(
        mp4=MP4Config(),
        gray_atkinson=GAConfig(),
        astral_3=ASTRAL3Config(is_exact=True),
    )
    assert isinstance(config_for(methods, TreeInferenceMethod.MP), MP4Config)
    assert isinstance(config_for(methods, TreeInferenceMethod.GA), GAConfig)
    assert isinstance(
        config_for(methods, TreeInferenceMethod.PCH_ASTRAL3), ASTRAL3Config
    )
    assert config_for(MethodConfig(), TreeInferenceMethod.MP) is None


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

    cfg = ExperimentConfig.model_validate(_config(tmp_path))
    out = handle_inference(cfg)

    assert out == tmp_path / "inference_data" / "inference_registry.csv"
    df = pl.read_csv(out)
    assert df.height == 1
    r = df.row(0, named=True)
    assert r["method"] == "mp"
    assert r["dataset_id"] == str(dataset)  # identity = the input path
    assert "poly_level" not in r and "fn_rate" not in r  # sim keys/FN-FP not here


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


def _setup(tmp_path: Path, methods: dict):
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
    return ExperimentConfig.model_validate(_config(tmp_path, methods=methods))


def _ok_infer(calls: list):
    # config_hash mirrors the real api.infer so resume (exact-config skip) works.
    def fake(input_csv, output_dir, method, config, *, name=None):
        calls.append(method)
        return InferenceResult(
            dataset_id=str(input_csv),
            tree_inference_method=method,
            config_hash=config_hash(config),
            method_config_json=config.model_dump_json(),
            point_estimate_newick="(A,B);",
            runtime_seconds=1.0,
            status=RunStatus.OK,
            ran_at=datetime.now(timezone.utc).isoformat(),
        )

    return fake


def test_handle_inference_skips_already_done(tmp_path: Path, monkeypatch):
    cfg = _setup(tmp_path, {"mp4": {}})
    calls: list = []
    monkeypatch.setattr(api, "infer", _ok_infer(calls))

    handle_inference(cfg)  # first run: MP4 runs, one row
    handle_inference(cfg)  # second run: already in the registry → skipped

    assert calls == [TreeInferenceMethod.MP]  # not re-run the second time
    df = pl.read_csv(tmp_path / "inference_data" / "inference_registry.csv")
    assert df.height == 1


def test_handle_inference_blocks_astral3_without_upstream(tmp_path: Path, monkeypatch):
    # Heuristic ASTRAL3 alone, no MP4/GA success anywhere → blocked, never run.
    cfg = _setup(tmp_path, {"astral_3": {"is_exact": False}})
    calls: list = []
    monkeypatch.setattr(api, "infer", _ok_infer(calls))

    out = handle_inference(cfg)

    assert calls == []  # blocked before api.infer
    assert pl.read_csv(out).height == 0  # nothing analyzable recorded


def test_handle_inference_omits_failed_from_registry(tmp_path: Path, monkeypatch):
    cfg = _setup(tmp_path, {"mp4": {}})
    calls: list = []

    def failed(input_csv, output_dir, method, config, *, name=None):
        calls.append(method)
        return InferenceResult(
            dataset_id=str(input_csv),
            tree_inference_method=method,
            config_hash=config_hash(config),
            method_config_json="{}",
            point_estimate_newick="",
            runtime_seconds=1.0,
            status=RunStatus.FAILED,
            ran_at=datetime.now(timezone.utc).isoformat(),
            log_path="/tmp/x.log",
        )

    monkeypatch.setattr(api, "infer", failed)

    out = handle_inference(cfg)

    assert calls == [TreeInferenceMethod.MP]  # it ran
    assert pl.read_csv(out).height == 0  # but failures aren't in the registry


def test_handle_inference_astral3_runs_when_upstream_ok_same_run(tmp_path, monkeypatch):
    # MP4 + GA succeed this run → heuristic ASTRAL3's gate passes → it IS invoked.
    cfg = _setup(
        tmp_path,
        {"mp4": {}, "gray_atkinson": {}, "astral_3": {"is_exact": False}},
    )
    calls: list = []
    monkeypatch.setattr(api, "infer", _ok_infer(calls))

    handle_inference(cfg)

    assert TreeInferenceMethod.PCH_ASTRAL3 in calls  # not blocked


def _setup_two_datasets(tmp_path: Path, methods: dict):
    # Two datasets under the same condition; mirrors _setup but with a 2nd row.
    cond = tmp_path / "simulation_data" / "simulated_data" / "high_0.1_4_320"
    cond.mkdir(parents=True)
    d1, d2 = cond / "sim_0_1_1.csv", cond / "sim_0_1_2.csv"
    d1.write_text("id,feature,weight,A,B\n")
    d2.write_text("id,feature,weight,A,B\n")
    base_tree = tmp_path / "base.txt"
    base_tree.write_text("(A,B);\n")
    pl.DataFrame(
        {"horizontal_edges": [0], "model_tree": [1], "path": [str(base_tree)]}
    ).write_csv(tmp_path / "simulation_data" / "model_graph_registry.csv")
    pl.DataFrame(
        {
            "poly_level": ["high", "high"],
            "character_count": [320, 320],
            "min_tree_height": [4, 4],
            "homoplasy_factor": [0.1, 0.1],
            "horizontal_edges": [0, 0],
            "model_tree": [1, 1],
            "replica": [1, 2],
            "path": [str(d1), str(d2)],
        }
    ).write_csv(tmp_path / "simulation_data" / "simulated_data_registry.csv")
    cfg = ExperimentConfig.model_validate(_config(tmp_path, methods=methods))
    return cfg, d1, d2


def test_handle_inference_datasets_subset(tmp_path: Path, monkeypatch):
    from scripts.lib.inference import registry

    cfg, d1, d2 = _setup_two_datasets(tmp_path, {"mp4": {}})
    ids: list = []

    def fake(input_csv, output_dir, method, config, *, name=None):
        ids.append(str(input_csv))
        return InferenceResult(
            dataset_id=str(input_csv),
            tree_inference_method=method,
            config_hash=config_hash(config),
            method_config_json=config.model_dump_json(),
            point_estimate_newick="(A,B);",
            runtime_seconds=1.0,
            status=RunStatus.OK,
            ran_at=datetime.now(timezone.utc).isoformat(),
        )

    monkeypatch.setattr(api, "infer", fake)

    subset = tmp_path / "subset.txt"
    subset.write_text(f"{d1}\n")  # name only d1
    handle_inference(cfg, datasets=subset)

    assert ids == [str(d1)]  # d2 skipped
    df = pl.read_csv(tmp_path / "inference_data" / "inference_registry.csv")
    assert df["dataset_id"].to_list() == [registry.canonical_path(d1)]


def test_handle_inference_method_filter(tmp_path: Path, monkeypatch):
    cfg = _setup(tmp_path, {"mp4": {}, "gray_atkinson": {}})
    calls: list = []
    monkeypatch.setattr(api, "infer", _ok_infer(calls))

    handle_inference(cfg, method="ga")

    assert calls == [TreeInferenceMethod.GA]  # only the named method runs


def test_handle_inference_method_not_enabled_errors(tmp_path: Path, monkeypatch):
    cfg = _setup(tmp_path, {"mp4": {}})
    monkeypatch.setattr(api, "infer", _ok_infer([]))

    with pytest.raises(AssertionError):
        handle_inference(cfg, method="ga")  # ga not enabled → error


def test_handle_inference_no_compact_skips_manifest(tmp_path: Path, monkeypatch):
    cfg = _setup(tmp_path, {"mp4": {}})
    calls: list = []
    monkeypatch.setattr(api, "infer", _ok_infer(calls))

    handle_inference(cfg, no_compact=True)

    inf = tmp_path / "inference_data"
    assert calls == [TreeInferenceMethod.MP]  # inference still ran
    assert not (inf / "inference_registry.csv").exists()  # not compacted
    assert not (inf / "manifest.json").exists()  # manifest untouched
    assert list((inf / "shards").glob("*.jsonl"))  # shards remain

    handle_inference(cfg, no_compact=False)  # default still compacts + writes manifest
    assert (inf / "inference_registry.csv").exists()
    assert (inf / "manifest.json").exists()


def test_handle_inference_astral3_runs_from_prior_registry(tmp_path, monkeypatch):
    # Cross-invocation: run 1 populates MP4+GA; run 2 is heuristic ASTRAL3 ALONE,
    # unblocked by the prior run's registry rows (the schema-alignment path).
    calls: list = []
    monkeypatch.setattr(api, "infer", _ok_infer(calls))

    handle_inference(_setup(tmp_path, {"mp4": {}, "gray_atkinson": {}}))
    assert set(calls) == {TreeInferenceMethod.MP, TreeInferenceMethod.GA}

    calls.clear()
    cfg2 = ExperimentConfig.model_validate(
        _config(tmp_path, methods={"astral_3": {"is_exact": False}})
    )
    handle_inference(cfg2)

    assert calls == [TreeInferenceMethod.PCH_ASTRAL3]  # deps satisfied by run 1
