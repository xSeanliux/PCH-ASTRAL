import subprocess
from pathlib import Path
from typing import TextIO

import pytest

from scripts.lib.experiment import MethodConfig, NetcsConfig
from scripts.lib.inference import api
from scripts.lib.inference.method_config import resolve_config
from scripts.lib.inference.runners.netcs import NetcsRunner
from scripts.lib.model.methods import (
    NetworkInferenceMethod,
    RunStatus,
    TreeInferenceMethod,
)

NETCS = NetworkInferenceMethod.NETCS

ROOTED = "(OUT,((a,(b)#H0),(c,(d,#H0))));"
# Real NetCS output: rerooted off the outgroup, leaving a unary `(OUT)`.
REROOTED = (
    "(t24,(t26,(((t27,(((((OUT),((((t14,t15),t11),t10),(t1,t2),(t4,t3))),"
    "(((t13,t12),t8),((t5,t6),t7))),((t30,t29),t16)))#H0),(t17,(t19,(t9,"
    "((((t28,t21),t23),((t20,t25),t18)),#H0))))),t22)));"
)
TREE = "(OUT,((a,b),(c,d)));"


def test_empty_yaml_block_yields_one_runner():
    methods = MethodConfig.model_validate({"netcs": {}})
    (runner,) = [r for c in methods.get_enabled_configs() for r in c.get_runners()]
    assert isinstance(runner, NetcsRunner)
    assert runner.method is NETCS
    assert runner.get_dependencies() == [TreeInferenceMethod.TOB_QMC]


def test_resolve_config_needs_no_file():
    assert resolve_config(NETCS, None) == NetcsConfig()


def test_build_argv(tmp_path: Path):
    argv = NetcsRunner(config=NetcsConfig()).build_argv(
        "r1", tmp_path / "d.csv", "d", tmp_path
    )
    assert argv[:2] == ["bash", "scripts/sh/runNETCS.sh"]
    assert argv[-2:] == ["--output", str(tmp_path)]


def _infer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, newick: str, returncode: int = 0
) -> api.InferenceResult:
    """`api.infer` with a `runNETCS.sh` that writes `newick`."""
    net = NetcsRunner.get_point_estimate_path(tmp_path, "d")

    def fake_run(
        argv: list[str], **_: int | TextIO
    ) -> subprocess.CompletedProcess[bytes]:
        net.parent.mkdir(parents=True, exist_ok=True)
        net.write_text(newick + "\n")
        return subprocess.CompletedProcess(argv, returncode)

    monkeypatch.setattr(subprocess, "run", fake_run)
    return api.infer(tmp_path / "d.csv", tmp_path, NetcsRunner(config=NetcsConfig()))


# REROOTED: the network is recorded as written, rooted on the outgroup or not.
@pytest.mark.parametrize("newick", [ROOTED, TREE, REROOTED])
def test_infer_records_network_as_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, newick: str
):
    result = _infer(tmp_path, monkeypatch, newick)
    assert result.status is RunStatus.OK
    assert result.point_estimate_newick == newick
    assert result.group_estimate_path is None


def test_infer_records_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    assert _infer(tmp_path, monkeypatch, ROOTED, returncode=1).status is RunStatus.FAILED
