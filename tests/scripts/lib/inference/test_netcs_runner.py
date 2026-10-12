import subprocess
from pathlib import Path
from typing import TextIO

import polars as pl
import pytest

from scripts.lib.experiment import MethodConfig, NetcsConfig
from scripts.lib.inference import api
from scripts.lib.inference.method_config import resolve_config
from scripts.lib.inference.runners.netcs import (
    NetcsRunner,
    is_rooted_on,
    netcs_to_family,
)
from scripts.lib.model.methods import (
    NetworkInferenceMethod,
    RunStatus,
    TreeInferenceMethod,
)
from scripts.lib.model.model_graph import ModelGraph
from scripts.py.cli.schemata import NETWORK_FAMILY_SCHEMA

NETCS = NetworkInferenceMethod.NETCS

ROOTED = "(OUT,((a,(b)#H0),(c,(d,#H0))));"
# Real NetCS output: rerooted off the outgroup, leaving a unary `(OUT)`.
REROOTED = (
    "(t24,(t26,(((t27,(((((OUT),((((t14,t15),t11),t10),(t1,t2),(t4,t3))),"
    "(((t13,t12),t8),((t5,t6),t7))),((t30,t29),t16)))#H0),(t17,(t19,(t9,"
    "((((t28,t21),t23),((t20,t25),t18)),#H0))))),t22)));"
)
TREE = "(OUT,((a,b),(c,d)));"


@pytest.mark.parametrize(
    ("newick", "label", "expected"),
    [
        (ROOTED, "OUT", True),
        (TREE, "OUT", True),
        ("((a,b),OUT);", "OUT", True),  # not the first root child
        (REROOTED, "OUT", False),
        ("((OUT),(a,b));", "OUT", False),  # unary root child is not the leaf
        ("(a,(OUT,b));", "OUT", False),
        ("(OUT2,(OUT,b));", "OUT", False),  # label is a prefix of another's
        ("(t10,(t1,b));", "t1", False),
        ("(t10,(t1,b));", "t10", True),
        ("(#H0,((a,(OUT)#H0),c));", "OUT", False),  # hybrid leaf at the root
    ],
)
def test_is_rooted_on(newick: str, label: str, expected: bool):
    assert is_rooted_on(newick, label) is expected


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


def test_family_matches_schema(tmp_path: Path):
    raw = tmp_path / "d.raw.net"
    raw.write_text(ROOTED + "\n")
    family = netcs_to_family(raw, "OUT")
    assert family.schema == NETWORK_FAMILY_SCHEMA
    assert family.rows() == [(1, ROOTED, True)]


def _infer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, newick: str, returncode: int = 0
) -> api.InferenceResult:
    """`api.infer` with a `runNETCS.sh` that writes `newick`; the outgroup is OUT."""
    raw = NetcsRunner.get_point_estimate_path(tmp_path, "d").with_name("d.raw.net")

    def fake_run(
        argv: list[str], **_: int | TextIO
    ) -> subprocess.CompletedProcess[bytes]:
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_text(newick + "\n")
        return subprocess.CompletedProcess(argv, returncode)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(
        ModelGraph,
        "from_dataset",
        lambda _: ModelGraph(1, 1, tmp_path / "net1-1.txt", "OUT"),
    )
    return api.infer(tmp_path / "d.csv", tmp_path, NetcsRunner(config=NetcsConfig()))


@pytest.mark.parametrize(("newick", "edges_added"), [(ROOTED, 1), (TREE, 0)])
def test_infer_records_rooted_network_and_family(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, newick: str, edges_added: int
):
    result = _infer(tmp_path, monkeypatch, newick)
    net = NetcsRunner.get_point_estimate_path(tmp_path, "d")
    family = NetcsRunner.get_group_estimate_path(tmp_path, "d")
    assert result.status is RunStatus.OK
    assert result.point_estimate_newick == net.read_text().strip() == newick
    assert result.group_estimate_path == str(family)
    assert pl.read_csv(family, schema=NETWORK_FAMILY_SCHEMA).rows() == [
        (edges_added, newick, True)
    ]


def test_infer_without_rooted_network_is_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    result = _infer(tmp_path, monkeypatch, REROOTED)
    family = NetcsRunner.get_group_estimate_path(tmp_path, "d")
    assert result.status is RunStatus.OK
    assert result.point_estimate_newick == ""
    assert not NetcsRunner.get_point_estimate_path(tmp_path, "d").exists()
    assert pl.read_csv(family)["is_best"].to_list() == [False]


def test_infer_records_failure_without_family(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    result = _infer(tmp_path, monkeypatch, ROOTED, returncode=1)
    assert result.status is RunStatus.FAILED
    assert result.group_estimate_path is None
    assert not NetcsRunner.get_group_estimate_path(tmp_path, "d").exists()
