import subprocess
from pathlib import Path
from typing import TextIO

import pytest
from pydantic import ValidationError

from scripts.lib.experiment import CamusConfig
from scripts.lib.inference import api
from scripts.lib.model.guide_tree import CAMUS_GUIDE_TREES, TRUE_TREE, GuideTree
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
    assert guide not in CAMUS_GUIDE_TREES
    with pytest.raises(ValidationError, match="unsupported guide tree"):
        _config(guide)


@pytest.mark.parametrize("guide", ["mp", "ga", "pch_w_tree_qmc"])
def test_unsupported_guides_are_rejected_from_yaml(guide: str):
    with pytest.raises(ValidationError, match="unsupported guide tree"):
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


def _bi_config(*is_bidirectional: bool) -> CamusConfig:
    return CamusConfig(
        guide_trees=frozenset({TRUE_TREE, ASTRAL3}),
        outgroup_label="OUT",
        bidirectional=frozenset(is_bidirectional),
    )


def test_get_runners_fan_out_guide_by_direction():
    runners = _bi_config(True, False).get_runners()
    assert [r.suffix for r in runners] == [
        "pch_astral3",
        "pch_astral3.bi",
        "true_tree",
        "true_tree.bi",
    ]
    assert [r.config.bidirectional for r in runners] == [{False}, {True}] * 2
    assert len({hash_config(r.config) for r in runners}) == 4


def test_unidirectional_hash_predates_the_field():
    # Pre-`bidirectional` hash: uni runs must not rerun.
    (r,) = _config(TRUE_TREE).get_runners()
    assert r.config.model_dump_json() == (
        '{"guide_trees":["true_tree"],"outgroup_label":"OUT"}'
    )
    assert hash_config(r.config) == (
        "36c0eecb2ad61dea498fefe60d927d36b60a147d5a2b48504b1ffed776c61b16"
    )


def test_build_argv_flags_only_bidirectional(tmp_path: Path):
    uni, bi = _bi_config(False, True).get_runners()[:2]
    assert "--bidirectional" not in uni.build_argv("r", tmp_path, "d", tmp_path)
    assert bi.build_argv("r", tmp_path, "d", tmp_path)[-1] == "--bidirectional"


def _fake_camus(family: Path, returncode: int):
    """A `subprocess.run` that writes CAMUS's raw CSV beside `family`."""

    def fake_run(
        argv: list[str], **_: int | TextIO
    ) -> subprocess.CompletedProcess[bytes]:
        family.parent.mkdir(parents=True, exist_ok=True)
        family.with_name("d.true_tree.csv").write_text(
            "Number of Branches,Quartet Satisfied Percent,Extended Newick\n"
            '0,0,"((A,B),(C,D));"\n'
        )
        return subprocess.CompletedProcess(argv, returncode)

    return fake_run


def test_execute_skips_family_on_camus_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    family = CamusRunner.get_group_estimate_path(tmp_path, "d.true_tree")
    monkeypatch.setattr(subprocess, "run", _fake_camus(family, 1))
    (runner,) = _config(TRUE_TREE).get_runners()
    with (tmp_path / "log").open("w") as log:
        assert (
            runner.execute("r", tmp_path / "d.csv", "d.true_tree", tmp_path, log) == 1
        )
    assert not family.exists()


def test_infer_records_group_estimate_and_no_newick(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    family = CamusRunner.get_group_estimate_path(tmp_path, "d.true_tree")
    monkeypatch.setattr(subprocess, "run", _fake_camus(family, 0))

    (runner,) = _config(TRUE_TREE).get_runners()
    result = api.infer(tmp_path / "d.csv", tmp_path, runner)
    assert result.status is RunStatus.OK
    assert result.point_estimate_newick == ""
    assert result.group_estimate_path == str(family)
    assert result.consensus_method is None


def test_infer_fails_when_no_family_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    def fake_run(
        argv: list[str], **_: int | TextIO
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    (runner,) = _config(TRUE_TREE).get_runners()
    result = api.infer(tmp_path / "d.csv", tmp_path, runner)
    assert result.status is RunStatus.FAILED
    assert result.group_estimate_path is None
