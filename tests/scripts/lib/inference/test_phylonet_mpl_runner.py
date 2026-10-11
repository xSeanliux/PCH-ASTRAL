import subprocess
from collections import Counter
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from scripts.lib.experiment import ExperimentConfig, PhyloNetMPLConfig
from scripts.lib.inference import api
from scripts.lib.inference.runners.phylonet_mpl import PhyloNetMPLRunner
from scripts.lib.model.guide_tree import (
    GUIDE_TREES,
    PHYLONET_MPL_GUIDE_TREES,
    TRUE_TREE,
    GuideTree,
)
from scripts.lib.model.methods import RunStatus, TreeInferenceMethod
from scripts.lib.types import Quartet
from scripts.py.phylonet_mpl_nexus import root_quartets

SPEC = Path("experiments/phylonet_mpl_smoke/experiment_specification.yaml")
WASTRAL = TreeInferenceMethod.PCH_WASTRAL


def _runner(guide: GuideTree = WASTRAL) -> PhyloNetMPLRunner:
    return PhyloNetMPLRunner(PhyloNetMPLConfig(guide_trees=frozenset({guide})))


def test_get_runners_split_per_guide_with_their_dependencies():
    config = PhyloNetMPLConfig(guide_trees=frozenset({WASTRAL, TRUE_TREE}))
    runners = config.get_runners()
    assert all(isinstance(r, PhyloNetMPLRunner) for r in runners)
    assert [r.suffix for r in runners] == ["pch_wastral", "true_tree"]
    assert [r.get_dependencies() for r in runners] == [[WASTRAL], []]


@pytest.mark.parametrize("guide", sorted(GUIDE_TREES - PHYLONET_MPL_GUIDE_TREES))
def test_guides_with_polytomies_are_rejected(guide: GuideTree):
    # -fs fixes the tree: a polytomy resolved by guide_tree.py would stay arbitrary.
    with pytest.raises(ValidationError, match="unsupported PhyloNet-MPL guide"):
        PhyloNetMPLConfig(guide_trees=frozenset({guide}))


def test_build_argv_passes_the_guide(tmp_path: Path):
    argv = _runner().build_argv("r1", tmp_path / "d.csv", "d.pch_wastral", tmp_path)
    assert argv[:2] == ["bash", "scripts/sh/runPhyloNetMPL.sh"]
    assert argv[-2:] == ["--guide-tree", "pch_wastral"]


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


def test_infer_records_best_network_and_family(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    net = PhyloNetMPLRunner.get_point_estimate_path(tmp_path, "d.pch_wastral")
    family = PhyloNetMPLRunner.get_group_estimate_path(tmp_path, "d.pch_wastral")
    newick = "((a,(b)#H1:1.0::0.7),(#H1:0.5::0.3,c));"

    def fake_run(argv: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        net.parent.mkdir(parents=True, exist_ok=True)
        net.write_text(newick + "\n")
        family.write_text(f"edges_added,network_newick\n1,{newick}\n")
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = api.infer(tmp_path / "d.csv", tmp_path, _runner())
    assert result.status is RunStatus.OK
    assert result.point_estimate_newick == newick  # as written
    assert result.group_estimate_path == str(family)
