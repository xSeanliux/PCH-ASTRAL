import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from scripts.lib.experiment import CamusConfig
from scripts.lib.inference import api
from scripts.lib.model.guide_tree import SUPPORTED_GUIDE_TREES, TRUE_TREE, GuideTree
from scripts.lib.model.methods import RunStatus, TreeInferenceMethod
from scripts.lib.inference.method_config import hash_config
from scripts.lib.inference.runners.camus import CamusRunner

ASTRAL3 = TreeInferenceMethod.PCH_ASTRAL3
WASTRAL = TreeInferenceMethod.PCH_WASTRAL


def _config(*guides: GuideTree) -> CamusConfig:
    return CamusConfig(guide_trees=frozenset(guides), outgroup_label="OUT")


@pytest.mark.parametrize(
    "guide",
    [
        TreeInferenceMethod.MP,
        TreeInferenceMethod.GA,
        TreeInferenceMethod.PCH_W_TREE_QMC,
    ],
)
def test_unsupported_guides_are_rejected(guide: GuideTree):
    # CAMUS refuses a non-binary/unrooted guide tree: mp is a majority consensus
    # (polytomies), ga is unrooted, and TREE-QMC can emit polytomies. Fail at
    # config load, not mid-run.
    assert guide not in SUPPORTED_GUIDE_TREES
    with pytest.raises(ValidationError, match="unsupported CAMUS guide tree"):
        _config(guide)


@pytest.mark.parametrize("guide", ["mp", "ga", "pch_w_tree_qmc"])
def test_unsupported_guides_are_rejected_from_yaml(guide: str):
    with pytest.raises(ValidationError, match="unsupported CAMUS guide tree"):
        CamusConfig.model_validate({"guide_trees": [guide], "outgroup_label": "OUT"})


def test_no_guides_is_rejected():
    with pytest.raises(ValidationError):
        _config()


def test_yaml_list_loads_as_a_set():
    config = CamusConfig.model_validate(
        {
            "guide_trees": ["true_tree", "pch_astral3", "true_tree"],
            "outgroup_label": "OUT",
        }
    )
    assert config.guide_trees == {ASTRAL3, TRUE_TREE}


def test_get_runners_dependencies_drop_true_tree():
    config = _config(ASTRAL3, TRUE_TREE, WASTRAL)
    deps = {r.guide: r.get_dependencies() for r in config.get_runners()}
    assert deps[ASTRAL3] == [ASTRAL3]
    assert deps[TRUE_TREE] == []
    assert deps[WASTRAL] == [WASTRAL]


def test_get_runners_split_per_guide_in_fixed_order():
    runners = _config(TRUE_TREE, ASTRAL3).get_runners()
    assert [r.suffix for r in runners] == ["pch_astral3", "true_tree"]
    assert [r.config.guide_trees for r in runners] == [{ASTRAL3}, {TRUE_TREE}]
    assert len({hash_config(r.config) for r in runners}) == 2


def test_camus_runner_hash_config_matches_single_guide_config():
    (r,) = _config(ASTRAL3).get_runners()
    assert hash_config(r.config) == hash_config(_config(ASTRAL3))
    assert r.config == _config(ASTRAL3)


def test_build_argv_passes_one_guide_and_the_outgroup(tmp_path: Path):
    (runner,) = _config(TRUE_TREE).get_runners()
    argv = runner.build_argv("r1", tmp_path / "d.csv", "d.true_tree", tmp_path)
    assert argv[-4:] == ["--guide-tree", "true_tree", "--outgroup", "OUT"]


def test_infer_records_group_estimate_and_no_newick(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    family = CamusRunner.get_group_estimate_path(tmp_path, "d.true_tree")

    def fake_run(argv: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        family.parent.mkdir(parents=True, exist_ok=True)
        family.write_text(
            "Number of Branches,Quartet Satisfied Percent,Extended Newick\n"
            '0,0,"((A,B),(C,D));"\n'
        )
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    (runner,) = _config(TRUE_TREE).get_runners()
    result = api.infer(tmp_path / "d.csv", tmp_path, runner)
    assert result.status is RunStatus.OK
    assert result.point_estimate_newick == ""
    assert result.group_estimate_path == str(family)
    assert result.consensus_method is None


def test_infer_fails_when_no_family_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    def fake_run(argv: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    (runner,) = _config(TRUE_TREE).get_runners()
    result = api.infer(tmp_path / "d.csv", tmp_path, runner)
    assert result.status is RunStatus.FAILED
    assert result.group_estimate_path is None
