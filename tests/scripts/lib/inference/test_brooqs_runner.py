import subprocess
from pathlib import Path
from typing import IO

import polars as pl
import pytest

from scripts.lib.experiment import BrooqsConfig, MethodConfig
from scripts.lib.inference import api
from scripts.lib.inference.method_config import resolve_config
from scripts.lib.inference.runners.brooqs import BrooqsRunner, brooqs_to_family
from scripts.lib.model.methods import (
    NetworkInferenceMethod,
    RunStatus,
    TreeInferenceMethod,
)
from scripts.py.cli.schemata import NETWORK_FAMILY_SCHEMA

BROOQS = NetworkInferenceMethod.BROOQS
NETWORK = "(OUT,(((A,(B)#H0),#H0),((C)#H1,(D,(E,#H1)))));"


def _stub_brooqs(
    monkeypatch: pytest.MonkeyPatch, net: Path, returncode: int = 0
) -> None:
    """Stub `subprocess.run` to write the `.net` BROOQS would and exit `returncode`."""

    def fake_run(
        argv: list[str], check: bool, stdout: IO[str], stderr: int
    ) -> subprocess.CompletedProcess[bytes]:
        """Write the network BROOQS would."""
        net.parent.mkdir(parents=True, exist_ok=True)
        net.write_text(NETWORK + "\n")
        return subprocess.CompletedProcess(argv, returncode)

    monkeypatch.setattr(subprocess, "run", fake_run)


def _infer(tmp_path: Path) -> api.InferenceResult:
    """Run the real runner on a dataset named `d`."""
    return api.infer(tmp_path / "d.csv", tmp_path, BrooqsRunner(config=BrooqsConfig()))


def test_empty_yaml_block_yields_one_runner():
    methods = MethodConfig.model_validate({"brooqs": {}})
    (runner,) = [r for c in methods.get_enabled_configs() for r in c.get_runners()]
    assert isinstance(runner, BrooqsRunner)
    assert runner.method is BROOQS
    assert runner.get_dependencies() == [TreeInferenceMethod.TOB_QMC]


def test_resolve_config_needs_no_file():
    assert resolve_config(BROOQS, None) == BrooqsConfig()


def test_build_argv(tmp_path: Path):
    argv = BrooqsRunner(config=BrooqsConfig()).build_argv(
        "r1", tmp_path / "d.csv", "d", tmp_path
    )
    assert argv[:2] == ["bash", "scripts/sh/runBROOQS.sh"]
    assert argv[-2:] == ["--output", str(tmp_path)]


def test_infer_records_network_and_family(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _stub_brooqs(monkeypatch, BrooqsRunner.get_point_estimate_path(tmp_path, "d"))
    result = _infer(tmp_path)
    assert result.status is RunStatus.OK
    assert result.point_estimate_newick == NETWORK
    assert result.group_estimate_path is not None
    family = pl.read_csv(result.group_estimate_path)
    assert family.schema == NETWORK_FAMILY_SCHEMA
    assert family.rows() == [(2, NETWORK, True)]


def test_tree_has_no_edges_added(tmp_path: Path):
    net = tmp_path / "d.net"
    net.write_text("(OUT,((A,B),(C,D)));\n")
    assert brooqs_to_family(net)["edges_added"].to_list() == [0]


def test_failed_run_writes_no_family(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _stub_brooqs(monkeypatch, BrooqsRunner.get_point_estimate_path(tmp_path, "d"), 1)
    assert _infer(tmp_path).status is RunStatus.FAILED
    assert not BrooqsRunner.get_group_estimate_path(tmp_path, "d").exists()
