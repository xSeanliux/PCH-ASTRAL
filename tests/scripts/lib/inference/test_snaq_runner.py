import subprocess
from pathlib import Path

import pytest

from scripts.lib.experiment import MethodConfig, SnaqConfig
from scripts.lib.inference import api
from scripts.lib.inference.runners.snaq import SnaqRunner
from scripts.lib.model.methods import RunStatus, TreeInferenceMethod


def test_empty_yaml_block_is_one_run():
    config = MethodConfig.model_validate({"snaq": {}}).snaq
    assert config is not None
    (runner,) = config.get_runners()
    assert isinstance(runner, SnaqRunner)


def test_start_tree_is_a_dependency():
    assert SnaqRunner(SnaqConfig()).get_dependencies() == [
        TreeInferenceMethod.PCH_WASTRAL
    ]


def test_build_argv(tmp_path: Path):
    argv = SnaqRunner(SnaqConfig()).build_argv("r1", tmp_path / "d.csv", "d", tmp_path)
    assert argv[:2] == ["bash", "scripts/sh/runSNAQ.sh"]
    assert argv[argv.index("--input") + 1] == str(tmp_path / "d.csv")


def test_infer_records_best_network_and_family(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    best = SnaqRunner.get_point_estimate_path(tmp_path, "d")
    family = SnaqRunner.get_group_estimate_path(tmp_path, "d")
    newick = "((A,(B)#H1),(C,(D,#H1)),OUT);"

    def fake_run(argv: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        best.parent.mkdir(parents=True, exist_ok=True)
        best.write_text(newick + "\n")
        family.write_text(f"edges_added,network_newick\n1,{newick}\n")
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = api.infer(tmp_path / "d.csv", tmp_path, SnaqRunner(SnaqConfig()))
    assert result.status is RunStatus.OK
    assert result.point_estimate_newick == newick
    assert result.group_estimate_path == str(family)
