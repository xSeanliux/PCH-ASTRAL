from pathlib import Path

from scripts.lib.inference.runners import RUNNERS
from scripts.lib.inference.inference import TreeInferenceMethod


def test_mp4_runner_build_argv():
    runner = RUNNERS[TreeInferenceMethod.MP]
    argv = runner.build_argv(
        runid="abc123",
        input_csv=Path("data/sim_0_1_1.csv"),
        name="sim_0_1_1",
        output_dir=Path("out/high_0.1_4_320"),
    )
    assert argv == [
        "bash",
        "scripts/sh/runMP4.sh",
        "--runid",
        "abc123",
        "--input",
        "data/sim_0_1_1.csv",
        "--name",
        "sim_0_1_1",
        "--output",
        "out/high_0.1_4_320",
    ]


def test_mp4_runner_artifact_paths():
    runner = RUNNERS[TreeInferenceMethod.MP]
    out = Path("out/high_0.1_4_320")
    assert (
        runner.point_estimate_path(out, "sim_0_1_1")
        == out / "MP4" / "trees" / "sim_0_1_1-maj.tree"
    )
    assert (
        runner.group_estimate_path(out, "sim_0_1_1")
        == out / "MP4" / "trees" / "sim_0_1_1.trees"
    )
    assert runner.consensus_method() == "majority"
    assert runner.log_path(out, "sim_0_1_1") == out / "MP4" / "logs" / "sim_0_1_1.log"


def test_registry_has_mp4():
    # M1 wires MP4 only; later milestones add GA/ASTRAL3/wASTRAL/TREE-QMC.
    assert TreeInferenceMethod.MP in RUNNERS
