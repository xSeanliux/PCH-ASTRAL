import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from scripts.lib.experiment import CamusConfig
from scripts.lib.inference import api
from scripts.lib.model.methods import RunStatus, TreeInferenceMethod
from scripts.lib.inference.method_config import config_hash
from scripts.lib.inference.runners.camus import CamusRunner

G = CamusConfig.GuideTree


def _config(*guides: CamusConfig.GuideTree) -> CamusConfig:
    return CamusConfig(guide_trees=frozenset(guides))


@pytest.mark.parametrize("guide", [G.MP, G.GA, G.W_TREE_QMC])
def test_unsupported_guides_are_rejected(guide: CamusConfig.GuideTree):
    # CAMUS refuses a non-binary/unrooted guide tree: mp is a majority consensus
    # (polytomies), ga is unrooted, and TREE-QMC can emit polytomies. Fail at
    # config load, not mid-run.
    assert not guide.is_supported
    with pytest.raises(ValidationError, match="unsupported CAMUS guide tree"):
        _config(guide)


def test_no_guides_is_rejected():
    with pytest.raises(ValidationError):
        _config()


def test_yaml_list_loads_as_a_set():
    config = CamusConfig.model_validate(
        {"guide_trees": ["true_tree", "astral3", "true_tree"]}
    )
    assert config.guide_trees == {G.ASTRAL3, G.TRUE_TREE}


def test_get_runners_dependencies_drop_true_tree():
    config = _config(G.ASTRAL3, G.TRUE_TREE, G.WASTRAL)
    deps = {r.guide: r.dependencies() for r in config.get_runners()}
    assert deps[G.ASTRAL3] == [TreeInferenceMethod.PCH_ASTRAL3]
    assert deps[G.TRUE_TREE] == []
    assert deps[G.WASTRAL] == [TreeInferenceMethod.PCH_WASTRAL]


@pytest.mark.parametrize(
    ("guide", "dependency"),
    [
        (G.ASTRAL3, TreeInferenceMethod.PCH_ASTRAL3),
        (G.WASTRAL, TreeInferenceMethod.PCH_WASTRAL),
        (G.TRUE_TREE, None),
    ],
)
def test_each_guide_names_its_source(
    guide: CamusConfig.GuideTree, dependency: TreeInferenceMethod | None
):
    assert guide.dependency is dependency


def test_get_runners_split_per_guide_in_fixed_order():
    runners = _config(G.TRUE_TREE, G.ASTRAL3).get_runners()
    assert [r.suffix for r in runners] == ["astral3", "true_tree"]
    assert [r.config.guide_trees for r in runners] == [{G.ASTRAL3}, {G.TRUE_TREE}]
    assert len({config_hash(r.config) for r in runners}) == 2


def test_camus_runner_config_hash_matches_single_guide_config():
    (r,) = _config(G.ASTRAL3).get_runners()
    assert config_hash(r.config) == config_hash(_config(G.ASTRAL3))
    assert r.config == _config(G.ASTRAL3)


def test_build_argv_passes_one_guide(tmp_path: Path):
    (runner,) = _config(G.TRUE_TREE).get_runners()
    argv = runner.build_argv("r1", tmp_path / "d.csv", "d.true_tree", tmp_path)
    assert argv[-2:] == ["--guide-tree", "true_tree"]


def test_infer_records_family_path_and_no_newick(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    family = CamusRunner.family_path(tmp_path, "d.true_tree")

    def fake_run(argv: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        family.parent.mkdir(parents=True, exist_ok=True)
        family.write_text(
            "Number of Branches,Quartet Satisfied Percent,Extended Newick\n"
            '0,0,"((A,B),(C,D));"\n'
        )
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    (runner,) = _config(G.TRUE_TREE).get_runners()
    result = api.infer(
        tmp_path / "d.csv",
        tmp_path,
        runner,
        name="d.true_tree",
    )
    assert result.status is RunStatus.OK
    assert result.point_estimate_newick == ""
    assert result.tree_set_path == str(family)
    assert result.consensus_method is None


def test_infer_fails_when_no_family_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    def fake_run(argv: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    (runner,) = _config(G.TRUE_TREE).get_runners()
    result = api.infer(tmp_path / "d.csv", tmp_path, runner)
    assert result.status is RunStatus.FAILED
    assert result.tree_set_path is None
