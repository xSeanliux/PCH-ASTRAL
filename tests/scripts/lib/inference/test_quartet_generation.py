import subprocess
from pathlib import Path
from typing import TextIO

import pytest
from pydantic import ValidationError

from scripts.lib.experiment import (
    BrooqsConfig,
    CamusConfig,
    NetcsConfig,
    RunnableConfig,
    SnaqConfig,
    TobQmcConfig,
)
from scripts.lib.inference.method_config import hash_config
from scripts.lib.model.methods import TreeInferenceMethod
from scripts.lib.pch import STRATEGY_TO_SCHEME
from scripts.lib.model.strategies import QuartetGenerationStrategy
from scripts.lib.types import Dataset

PCH_W, PCH_W_N = QuartetGenerationStrategy.PCH_W, QuartetGenerationStrategy.PCH_W_N
BOTH = ["PCH_W", "PCH_W_N"]


@pytest.mark.parametrize(
    ("config_class", "extra"),
    [(CamusConfig, {"outgroup_label": "OUT"}), (SnaqConfig, {})],
)
def test_guided_runs_every_guide_and_strategy(
    config_class: type[RunnableConfig], extra: dict[str, str]
):
    config = config_class.model_validate(
        {"guide_trees": ["pch_astral3", "true_tree"], "quartet_generation": BOTH}
        | extra
    )
    runners = config.get_runners()
    # PCH_W keeps the pre-strategy names, so old outputs still match.
    assert sorted(r.get_run_name("d") for r in runners) == [
        "d.pch_astral3",
        "d.pch_astral3.PCH_W_N",
        "d.true_tree",
        "d.true_tree.PCH_W_N",
    ]
    assert len({hash_config(r.config) for r in runners}) == 4


def test_tob_qmc_runs_one_per_strategy():
    config = TobQmcConfig.model_validate({"quartet_generation": BOTH})
    assert [r.get_run_name("d") for r in config.get_runners()] == ["d", "d.PCH_W_N"]


@pytest.mark.parametrize("config_class", [BrooqsConfig, NetcsConfig])
def test_consumer_reads_matching_tree_of_blobs(
    config_class: type[RunnableConfig], tmp_path: Path
):
    pch_w, pch_w_n = config_class.model_validate(
        {"quartet_generation": BOTH}
    ).get_runners()
    # PCH_W keeps its name and hash (#73's dump); PCH_W_N differs from #73's.
    assert pch_w.config.model_dump_json() == '{"quartet_generation":["PCH_W"]}'
    assert pch_w_n.config.model_dump_json() == (
        '{"quartet_generation":["PCH_W_N"],"tree_of_blobs":"PCH_W_N"}'
    )
    assert [pch_w.get_run_name("d"), pch_w_n.get_run_name("d")] == [
        "d",
        "d.PCH_W_N.tob_PCH_W_N",
    ]
    tob = TreeInferenceMethod.TOB_QMC
    assert pch_w.get_dependency_suffixes() == {tob: None}
    assert pch_w_n.get_dependency_suffixes() == {tob: "PCH_W_N"}
    trees = tmp_path / "TOB_QMC" / "trees"
    for runner, tree in [(pch_w, "d.tree"), (pch_w_n, "d.PCH_W_N.tree")]:
        argv = runner.build_argv("r", tmp_path / "d.csv", "d", tmp_path)
        assert argv[argv.index("--tree-of-blobs") + 1] == str(trees / tree)


def test_tob_qmc_default_keeps_its_hash():
    """PCH_W stays out of the dump, so pre-strategy tob_qmc rows still resume."""
    (pch_w, pch_w_n) = TobQmcConfig.model_validate(
        {"quartet_generation": BOTH}
    ).get_runners()
    old = '{"alpha":1e-7,"three_fix_one_alter":true}'
    assert TobQmcConfig().model_dump_json() == pch_w.config.model_dump_json() == old
    assert "PCH_W_N" in pch_w_n.config.model_dump_json()
    assert TobQmcConfig.model_validate_json(old) == TobQmcConfig()


def test_no_strategy_is_rejected():
    with pytest.raises(ValidationError):
        BrooqsConfig.model_validate({"quartet_generation": []})


# a,b share state 1, d,e state 2; c has both, so the schemes disagree.
OVERLAP_CSV = "id,feature,weight,a,b,c,d,e\nx,f,1,1,1,1/2,2,2\n"


def test_script_reads_the_strategys_quartets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("PCH_SCRATCH", str(tmp_path))
    csv = tmp_path / "d.csv"
    csv.write_text(OVERLAP_CSV)
    seen: list[int] = []

    def fake_run(
        argv: list[str], **_: bool | TextIO | int
    ) -> subprocess.CompletedProcess[bytes]:
        quartets = Path(argv[argv.index("--quartets") + 1])
        seen.append(len(quartets.read_text().splitlines()))
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    both = frozenset({PCH_W, PCH_W_N})
    runners = [
        *BrooqsConfig(quartet_generation=both).get_runners(),
        *TobQmcConfig(quartet_generation=both).get_runners(),
    ]
    for runner in runners:
        with (tmp_path / "log").open("w") as log:
            assert runner.execute("r", csv, "d", tmp_path, log) == 0
    # One line per unit of weight, per each scheme.
    dataset = Dataset.from_path(csv)
    assert seen == 2 * [
        sum(STRATEGY_TO_SCHEME[q].get_quartets(dataset).values())
        for q in (PCH_W, PCH_W_N)
    ]
    assert seen[0] != seen[1]
