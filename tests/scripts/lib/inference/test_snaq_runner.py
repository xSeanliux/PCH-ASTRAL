import subprocess
from pathlib import Path
from typing import TextIO

import polars as pl
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


NEWICK = "((A,(B)#H1),(C,(D,#H1)),OUT);"


def _fake_snaq(networks_dir: Path, choice: str, returncode: int = 0):
    """A `subprocess.run` that writes SNaQ's raw output for `d.pch_wastral`."""

    def fake_run(
        argv: list[str], **_: int | TextIO
    ) -> subprocess.CompletedProcess[bytes]:
        networks_dir.mkdir(parents=True, exist_ok=True)
        prefix = networks_dir / "d.pch_wastral"
        Path(f"{prefix}.networks").write_text(f"{NEWICK}, with -loglik 1.5\n")
        Path(f"{prefix}.choice").write_text(f"{choice}\n")
        if choice != "none":
            Path(f"{prefix}.net").write_text(NEWICK + "\n")
        return subprocess.CompletedProcess(argv, returncode)

    return fake_run


def test_execute_skips_family_on_snaq_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    family = SnaqRunner.get_group_estimate_path(tmp_path, "d.pch_wastral")
    monkeypatch.setattr(subprocess, "run", _fake_snaq(family.parent, "0", 1))
    with (tmp_path / "log").open("w") as log:
        assert (
            _runner().execute("r", tmp_path / "d.csv", "d.pch_wastral", tmp_path, log)
            == 1
        )
    assert not family.exists()


def test_infer_records_best_network_and_family(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    family = SnaqRunner.get_group_estimate_path(tmp_path, "d.pch_wastral")
    monkeypatch.setattr(subprocess, "run", _fake_snaq(family.parent, "0"))
    result = api.infer(tmp_path / "d.csv", tmp_path, _runner())
    assert result.status is RunStatus.OK
    assert result.point_estimate_newick == NEWICK
    assert result.group_estimate_path == str(family)
    assert pl.read_csv(family)["is_best"].to_list() == [True]


def test_infer_without_consistent_network_is_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    family = SnaqRunner.get_group_estimate_path(tmp_path, "d.pch_wastral")
    monkeypatch.setattr(subprocess, "run", _fake_snaq(family.parent, "none"))
    result = api.infer(tmp_path / "d.csv", tmp_path, _runner())
    assert result.status is RunStatus.OK
    assert result.point_estimate_newick == ""
    assert result.group_estimate_path == str(family)
    assert pl.read_csv(family)["is_best"].to_list() == [False]
