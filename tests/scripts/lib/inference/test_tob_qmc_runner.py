import subprocess
from pathlib import Path
from typing import IO

import pytest

from scripts.lib.experiment import MethodConfig, TobQmcConfig
from scripts.lib.inference import api
from scripts.lib.inference.method_config import resolve_config
from scripts.lib.inference.runners.tob_qmc import TobQmcRunner
from scripts.lib.model.methods import NetworkInferenceMethod, RunStatus

TOB_QMC = NetworkInferenceMethod.TOB_QMC


def test_empty_yaml_block_yields_one_runner():
    methods = MethodConfig.model_validate({"tob_qmc": {}})
    (runner,) = [r for c in methods.get_enabled_configs() for r in c.get_runners()]
    assert isinstance(runner, TobQmcRunner)
    assert runner.method is TOB_QMC
    assert runner.get_dependencies() == []


def test_resolve_config_needs_no_file():
    assert resolve_config(TOB_QMC, None) == TobQmcConfig()


def test_build_argv(tmp_path: Path):
    argv = TobQmcRunner(config=TobQmcConfig()).build_argv(
        "r1", tmp_path / "d.csv", "d", tmp_path
    )
    assert argv[:2] == ["bash", "scripts/sh/runTOBQMC.sh"]
    assert argv[-2:] == ["--output", str(tmp_path)]


def test_infer_records_tree_of_blobs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    tob = TobQmcRunner.get_point_estimate_path(tmp_path, "d")

    def fake_run(
        argv: list[str], check: bool, stdout: IO[str], stderr: int
    ) -> subprocess.CompletedProcess[bytes]:
        """Write the tree TREE-QMC would."""
        tob.parent.mkdir(parents=True, exist_ok=True)
        tob.write_text("((A,B),C,D,E);\n")
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = api.infer(
        tmp_path / "d.csv", tmp_path, TobQmcRunner(config=TobQmcConfig())
    )
    assert result.status is RunStatus.OK
    assert result.point_estimate_newick == "((A,B),C,D,E);"
    assert result.group_estimate_path is None
