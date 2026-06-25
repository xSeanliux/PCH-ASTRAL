from datetime import datetime, timezone
from pathlib import Path

from typer.testing import CliRunner

from scripts.lib.inference import api
from scripts.lib.inference.inference import InferenceResult, TreeInferenceMethod
from scripts.py.cli import main

runner = CliRunner()


def _result() -> InferenceResult:
    return InferenceResult(
        dataset_id="d",
        tree_inference_method=TreeInferenceMethod.MP,
        config_hash="h",
        method_config_json="{}",
        point_estimate_newick="(A,B);",
        runtime_seconds=1.0,
        status="ok",
        ran_at=datetime.now(timezone.utc).isoformat(),
    )


def test_infer_command_invokes_api(tmp_path: Path, monkeypatch):
    calls = {}

    def fake_infer(input_csv, output_dir, method, config, *, name=None):
        calls["method"] = method
        return _result()

    monkeypatch.setattr(api, "infer", fake_infer)
    res = runner.invoke(main.app, ["infer", "in.csv", str(tmp_path), "--json"])
    assert res.exit_code == 0, res.output
    assert calls["method"] == TreeInferenceMethod.MP
    assert '"method": "mp"' in res.output


def test_experiment_inference_invokes_handler(monkeypatch):
    called = {}

    def fake_handle(cfg):
        called["yes"] = True
        return Path("out.csv")

    monkeypatch.setattr(main, "handle_inference", fake_handle)
    monkeypatch.setattr(main, "_get_experiment_config", lambda p: object())
    res = runner.invoke(main.app, ["experiment", "inference", "spec.yaml"])
    assert res.exit_code == 0, res.output
    assert called.get("yes")
