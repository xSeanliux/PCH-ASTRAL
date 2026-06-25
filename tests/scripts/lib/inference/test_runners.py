from pathlib import Path

import pytest

from scripts.lib.inference import runners
from scripts.lib.inference.inference import TreeInferenceMethod


def test_build_mp4_argv():
    argv = runners.build_argv(
        TreeInferenceMethod.MP,
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


def test_mp4_artifact_paths():
    out = Path("out/high_0.1_4_320")
    assert (
        runners.point_estimate_path(TreeInferenceMethod.MP, out, "sim_0_1_1")
        == out / "MP4" / "trees" / "sim_0_1_1-maj.tree"
    )
    assert (
        runners.group_estimate_path(TreeInferenceMethod.MP, out, "sim_0_1_1")
        == out / "MP4" / "trees" / "sim_0_1_1.trees"
    )
    assert runners.consensus_method(TreeInferenceMethod.MP) == "majority"
    assert (
        runners.log_path(TreeInferenceMethod.MP, out, "sim_0_1_1")
        == out / "MP4" / "logs" / "sim_0_1_1.log"
    )


def test_unimplemented_method_raises():
    with pytest.raises(NotImplementedError):
        runners.build_argv(TreeInferenceMethod.GA, "x", Path("a.csv"), "a", Path("o"))
    with pytest.raises(NotImplementedError):
        runners.point_estimate_path(TreeInferenceMethod.GA, Path("o"), "a")
    with pytest.raises(NotImplementedError):
        runners.group_estimate_path(TreeInferenceMethod.GA, Path("o"), "a")
    with pytest.raises(NotImplementedError):
        runners.consensus_method(TreeInferenceMethod.GA)
    with pytest.raises(NotImplementedError):
        runners.log_path(TreeInferenceMethod.GA, Path("o"), "a")
