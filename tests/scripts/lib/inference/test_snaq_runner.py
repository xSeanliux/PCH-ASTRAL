import subprocess
from pathlib import Path

import pytest

from pydantic import ValidationError

from scripts.lib.experiment import MethodConfig, SnaqConfig
from scripts.lib.inference import api
from scripts.lib.inference.method_config import hash_config
from scripts.lib.inference.runners.snaq import SnaqRunner
from scripts.lib.model.guide_tree import GUIDE_TREES, TRUE_TREE, GuideTree
from scripts.lib.model.methods import RunStatus, TreeInferenceMethod

MP = TreeInferenceMethod.MP
WASTRAL = TreeInferenceMethod.PCH_WASTRAL


def _runner(guide: GuideTree = WASTRAL) -> SnaqRunner:
    return SnaqRunner(SnaqConfig(guide_trees=frozenset({guide})))


def test_yaml_block_is_one_run_per_guide():
    config = MethodConfig.model_validate({"snaq": {"guide_trees": ["mp"]}}).snaq
    assert config is not None
    (runner,) = config.get_runners()
    assert isinstance(runner, SnaqRunner)


@pytest.mark.parametrize("block", [{}, {"guide_trees": []}, {"guide_trees": ["x"]}])
def test_missing_or_unknown_guides_are_rejected(block: dict[str, list[str]]):
    with pytest.raises(ValidationError):
        SnaqConfig.model_validate(block)


def test_every_guide_is_supported():
    # snaq! resolves polytomies and unroots its start tree (SNaQ readTopologyUpdate).
    assert SnaqConfig(guide_trees=GUIDE_TREES).guide_trees == GUIDE_TREES


def test_get_runners_split_per_guide_in_fixed_order():
    runners = SnaqConfig(guide_trees=frozenset({WASTRAL, MP, TRUE_TREE})).get_runners()
    assert [r.suffix for r in runners] == ["mp", "pch_wastral", "true_tree"]
    assert [r.get_dependencies() for r in runners] == [[MP], [WASTRAL], []]
    assert len({hash_config(r.config) for r in runners}) == 3
    assert runners[1].config == _runner().config  # same hash as a single-guide YAML


def test_build_argv_passes_the_guide(tmp_path: Path):
    argv = _runner(MP).build_argv("r1", tmp_path / "d.csv", "d.mp", tmp_path)
    assert argv[:2] == ["bash", "scripts/sh/runSNAQ.sh"]
    assert argv[argv.index("--input") + 1] == str(tmp_path / "d.csv")
    assert argv[-2:] == ["--guide-tree", "mp"]


def test_infer_records_best_network_and_family(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    best = SnaqRunner.get_point_estimate_path(tmp_path, "d.pch_wastral")
    family = SnaqRunner.get_group_estimate_path(tmp_path, "d.pch_wastral")
    newick = "((A,(B)#H1),(C,(D,#H1)),OUT);"

    def fake_run(argv: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        best.parent.mkdir(parents=True, exist_ok=True)
        best.write_text(newick + "\n")
        family.write_text(f"edges_added,network_newick\n1,{newick}\n")
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = api.infer(tmp_path / "d.csv", tmp_path, _runner())
    assert result.status is RunStatus.OK
    assert result.point_estimate_newick == newick
    assert result.group_estimate_path == str(family)


def test_infer_without_consistent_network_is_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    family = SnaqRunner.get_group_estimate_path(tmp_path, "d.pch_wastral")

    def fake_run(argv: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        family.parent.mkdir(parents=True, exist_ok=True)
        family.write_text(
            "edges_added,network_newick,is_best\n1,(A,(B)#H1,#H1);,false\n"
        )
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = api.infer(tmp_path / "d.csv", tmp_path, _runner())
    assert result.status is RunStatus.OK
    assert result.point_estimate_newick == ""
    assert result.group_estimate_path == str(family)
