import subprocess
from pathlib import Path
from typing import TextIO

import pytest

from scripts.lib.experiment import MethodConfig, NetcsConfig
from scripts.lib.inference import api
from scripts.lib.inference.method_config import resolve_config
from scripts.lib.inference.runners.netcs import NetcsRunner, reroot_on
from scripts.lib.model.methods import (
    NetworkInferenceMethod,
    RunStatus,
    TreeInferenceMethod,
)
from scripts.lib.model.model_graph import ModelGraph
from scripts.py.cli.handle_network_score import is_rooted_on

NETCS = NetworkInferenceMethod.NETCS
# Quartet-based runners read `d.csv` in `execute`.
pytestmark = pytest.mark.usefixtures("quartet_input")

ROOTED = "(OUT,((a,(b)#H0),(c,(d,#H0))));"
# Real NetCS output: rerooted off the outgroup, leaving a unary `(OUT)`.
REROOTED = (
    "(t24,(t26,(((t27,(((((OUT),((((t14,t15),t11),t10),(t1,t2),(t4,t3))),"
    "(((t13,t12),t8),((t5,t6),t7))),((t30,t29),t16)))#H0),(t17,(t19,(t9,"
    "((((t28,t21),t23),((t20,t25),t18)),#H0))))),t22)));"
)
TREE = "(OUT,((a,b),(c,d)));"
# Rooted elsewhere, the outgroup below no hybrid; its rerooting.
ROOTABLE = "((a,(b)#H0),((c,(d,#H0)),(OUT,e)));"
REROOTED_ON_OUT = "((((a,(b)#H0),(c,(d,#H0))),e),OUT);"


@pytest.mark.parametrize(
    ("newick", "expected"),
    [
        (ROOTABLE, REROOTED_ON_OUT),
        ("(a,(b)#H0,((c,(d,#H0)),(OUT,e)));", REROOTED_ON_OUT),  # trifurcating root
        (REROOTED, None),
        ("(a,((OUT)#H0,(c,(d,#H0))));", None),
    ],
)
def test_reroot_on(newick: str, expected: str | None):
    assert reroot_on(newick, "OUT") == expected


@pytest.mark.parametrize("newick", [ROOTED, TREE])
def test_reroot_on_keeps_a_rooted_network_rooted(newick: str):
    rerooted = reroot_on(newick, "OUT")
    assert rerooted is not None and is_rooted_on(rerooted, "OUT")


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
    assert argv[argv.index("--output") + 1] == str(tmp_path)


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
    monkeypatch.setattr(
        ModelGraph,
        "from_dataset",
        lambda _: ModelGraph(1, 1, tmp_path / "net1-1.txt", "OUT"),
    )
    return api.infer(tmp_path / "d.csv", tmp_path, NetcsRunner(config=NetcsConfig()))


# Rerooted on the outgroup if it can be; else recorded as NetCS wrote it.
@pytest.mark.parametrize(
    ("written", "recorded"), [(ROOTABLE, REROOTED_ON_OUT), (REROOTED, REROOTED)]
)
def test_infer_records_network_rerooted_if_possible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, written: str, recorded: str
):
    result = _infer(tmp_path, monkeypatch, written)
    assert result.status is RunStatus.OK
    assert result.point_estimate_newick == recorded
    assert result.group_estimate_path is None


def test_infer_records_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    assert (
        _infer(tmp_path, monkeypatch, ROOTED, returncode=1).status is RunStatus.FAILED
    )
