import subprocess
from pathlib import Path
from typing import TextIO

import polars as pl
import pytest
from pydantic import ValidationError

from scripts.lib.experiment import CamusBidirectionalConfig, CamusConfig
from scripts.lib.inference import api
from scripts.lib.model.guide_tree import CAMUS_GUIDE_TREES, TRUE_TREE, GuideTree
from scripts.lib.model.methods import (
    NetworkInferenceMethod,
    RunStatus,
    TreeInferenceMethod,
)
from scripts.lib.inference.method_config import METHOD_TO_CONFIG_CLASS, hash_config
from scripts.lib.inference.runners import METHOD_TO_RUNNER_CLASS
from scripts.lib.inference.scoring import ScoreResult, score_network
from tests.scripts.lib.inference.test_scoring import needs_phylonet
from scripts.lib.inference.runners.camus import (
    CamusBidirectionalRunner,
    CamusRunner,
    camus_to_family,
)

ASTRAL3 = TreeInferenceMethod.PCH_ASTRAL3
WASTRAL = TreeInferenceMethod.PCH_WASTRAL


def _config(*guides: GuideTree) -> CamusConfig:
    return CamusConfig(guide_trees=frozenset(guides), outgroup_label="OUT")


@pytest.mark.parametrize(
    "guide",
    [TreeInferenceMethod.MP, TreeInferenceMethod.GA],
)
def test_unsupported_guides_are_rejected(guide: GuideTree):
    # CAMUS refuses a non-binary/unrooted guide tree: mp is a majority consensus
    # (polytomies) and ga is unrooted. Fail at config load, not mid-run.
    assert guide not in CAMUS_GUIDE_TREES
    with pytest.raises(ValidationError, match="unsupported guide tree"):
        _config(guide)


@pytest.mark.parametrize("guide", ["mp", "ga"])
def test_unsupported_guides_are_rejected_from_yaml(guide: str):
    with pytest.raises(ValidationError, match="unsupported guide tree"):
        CamusConfig.model_validate({"guide_trees": [guide], "outgroup_label": "OUT"})


def test_tree_qmc_guide_is_accepted():
    # Its rare polytomy is resolved when the guide is built.
    assert _config(TreeInferenceMethod.PCH_W_TREE_QMC).get_runners()


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


def test_bidirectional_resolves_and_flags_b(tmp_path: Path):
    bi_method = NetworkInferenceMethod.CAMUS_BIDIRECTIONAL
    assert METHOD_TO_CONFIG_CLASS[bi_method] is CamusBidirectionalConfig
    assert METHOD_TO_RUNNER_CLASS[bi_method] is CamusBidirectionalRunner
    bi_config = CamusBidirectionalConfig(
        guide_trees=frozenset({TRUE_TREE}), outgroup_label="OUT"
    )
    (bi,) = bi_config.get_runners()
    (uni,) = _config(TRUE_TREE).get_runners()
    assert bi.method == bi_method
    uni_argv = uni.build_argv("r", tmp_path, "d", tmp_path)
    assert "--bidirectional" not in uni_argv
    assert bi.build_argv("r", tmp_path, "d", tmp_path) == uni_argv + ["--bidirectional"]


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


CAMUS_BIN = Path(__file__).parents[4] / "bin" / "camus"
# B and C are sisters in 8 of 20 non-OUT quartets: one B–C contact event.
GENE_TREES = (
    ["((A,B),(C,D));"] * 6
    + ["((A,B),(C,E));"] * 6
    + ["((B,C),(A,D));"] * 4
    + ["((B,C),(A,E));"] * 4
)


# The true network: one B–C event as two contact edges (ADR 0001).
TRUE_NETWORK = "((((A,((B)#H2,#H1)),((C)#H1,#H2)),(D,E)),OUT);"


@pytest.mark.skipif(not CAMUS_BIN.exists(), reason="needs bin/camus")
@needs_phylonet
def test_bin_camus_bidirectional_recovers_bidirectional_event(tmp_path: Path):
    """At k=1, only `-B` recovers a bidirectional event exactly.

    Fails on a pre-fork `bin/camus`: rerun `install_camus.sh`.
    """
    guide, genes = tmp_path / "guide.nwk", tmp_path / "genes.nwk"
    guide.write_text("((((A,B),C),(D,E)),OUT);\n")
    genes.write_text("\n".join(GENE_TREES) + "\n")

    def run(*flags: str) -> ScoreResult:
        """:returns: the k=1 network's score; CAMUS writes `<prefix>.csv`."""
        prefix = tmp_path / ("bi" if flags else "uni")
        cmd = [CAMUS_BIN, "-n", "1", *flags, "-o", prefix, guide, genes]
        subprocess.run(cmd, cwd=tmp_path, capture_output=True, check=True)
        family = camus_to_family(prefix.with_suffix(".csv"))
        (newick,) = family.filter(pl.col("edges_added") == 1)["network_newick"]
        return score_network(newick, TRUE_NETWORK)

    assert run("-B") == ScoreResult(0.0, 0.0)
    assert run() != ScoreResult(0.0, 0.0)
