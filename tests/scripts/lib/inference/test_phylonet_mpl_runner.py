import subprocess
from collections import Counter
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from scripts.lib.experiment import ExperimentConfig, PhyloNetMPLConfig
from scripts.lib.inference import api
from scripts.lib.inference.runners.phylonet_mpl import PhyloNetMPLRunner
from scripts.lib.model.methods import RunStatus, TreeInferenceMethod
from scripts.lib.types import Quartet
from scripts.py.phylonet_mpl_nexus import root_quartets

SPEC = Path("experiments/phylonet_mpl_smoke/experiment_specification.yaml")


def _runner() -> PhyloNetMPLRunner:
    (runner,) = PhyloNetMPLConfig.model_validate({}).get_runners()
    assert isinstance(runner, PhyloNetMPLRunner)
    return runner


def test_runner_depends_on_the_start_tree_method():
    assert _runner().get_dependencies() == [TreeInferenceMethod.PCH_WASTRAL]


def test_build_argv(tmp_path: Path):
    argv = _runner().build_argv("r1", tmp_path / "d.csv", "d", tmp_path)
    assert argv[:2] == ["bash", "scripts/sh/runPHYLONETMPL.sh"]
    assert argv[-2:] == ["--output", str(tmp_path)]


def test_smoke_spec_loads_and_outgroup_is_required():
    spec = yaml.safe_load(SPEC.read_text())
    assert ExperimentConfig.model_validate(spec).methods.phylonet_mpl is not None
    spec["simulation"]["outgroup_label"] = None
    with pytest.raises(ValidationError, match="needs simulation.outgroup_label"):
        ExperimentConfig.model_validate(spec)


def test_root_quartets_keeps_outgroup_quartets_rooted_and_weighted():
    quartets = Counter(
        {
            Quartet(("OUT", "a", "b", "c")): 2,  # ((OUT,a),(b,c))
            Quartet(("a", "b", "c", "d")): 5,  # no outgroup: unrootable, dropped
        }
    )
    assert root_quartets(quartets, "OUT") == ["(((b,c),a),OUT);"] * 2


def test_infer_records_network_as_group_estimate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    net = PhyloNetMPLRunner.get_group_estimate_path(tmp_path, "d")

    def fake_run(argv: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        net.parent.mkdir(parents=True, exist_ok=True)
        net.write_text("((a,(b)#H1),(#H1,c));\n")
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = api.infer(tmp_path / "d.csv", tmp_path, _runner())
    assert result.status is RunStatus.OK
    assert result.point_estimate_newick == ""  # tree scoring skips it
    assert result.group_estimate_path == str(net)
