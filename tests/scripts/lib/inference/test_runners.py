from pathlib import Path

import pytest

from scripts.lib.experiment import ASTRAL3Config, GAConfig, MP4Config
from scripts.lib.inference import runners
from scripts.lib.inference.inference import TreeInferenceMethod


def test_build_mp4_argv():
    argv = runners.build_argv(
        TreeInferenceMethod.MP,
        runid="abc123",
        input_csv=Path("data/sim_0_1_1.csv"),
        name="sim_0_1_1",
        output_dir=Path("out/high_0.1_4_320"),
        config=MP4Config(),
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


def test_build_ga_argv():
    argv = runners.build_argv(
        TreeInferenceMethod.GA,
        runid="abc123",
        input_csv=Path("data/sim_0_1_1.csv"),
        name="sim_0_1_1",
        output_dir=Path("out/high_0.1_4_320"),
        config=GAConfig(),
    )
    assert argv == [
        "bash",
        "scripts/sh/runGA.sh",
        "--runid",
        "abc123",
        "--input",
        "data/sim_0_1_1.csv",
        "--name",
        "sim_0_1_1",
        "--output",
        "out/high_0.1_4_320",
    ]


def test_ga_artifact_paths():
    out = Path("out/high_0.1_4_320")
    assert (
        runners.point_estimate_path(TreeInferenceMethod.GA, out, "sim_0_1_1")
        == out / "GA" / "trees" / "sim_0_1_1.tree"
    )
    assert (
        runners.group_estimate_path(TreeInferenceMethod.GA, out, "sim_0_1_1")
        == out / "GA" / "trees1" / "sim_0_1_1.trees"
    )
    assert runners.consensus_method(TreeInferenceMethod.GA) == "mcc"
    assert (
        runners.log_path(TreeInferenceMethod.GA, out, "sim_0_1_1")
        == out / "GA" / "logs" / "sim_0_1_1.log"
    )


def test_build_astral3_argv_exact():
    argv = runners.build_argv(
        TreeInferenceMethod.PCH_ASTRAL3,
        runid="abc123",
        input_csv=Path("data/sim_0_1_1.csv"),
        name="sim_0_1_1",
        output_dir=Path("out/high_0.1_4_320"),
        config=ASTRAL3Config(is_exact=True),
    )
    assert argv == [
        "bash",
        "scripts/sh/runASTRAL.sh",
        "-H",
        "abc123",
        "-i",
        "data/sim_0_1_1.csv",
        "-o",
        "out/high_0.1_4_320",
        "-q",
        "11",
        "-b",
        "5",
        "-n",
        "sim_0_1_1",
        "-x",
    ]


def test_build_astral3_argv_heuristic_has_no_x():
    argv = runners.build_argv(
        TreeInferenceMethod.PCH_ASTRAL3,
        runid="abc123",
        input_csv=Path("data/sim_0_1_1.csv"),
        name="sim_0_1_1",
        output_dir=Path("out/high_0.1_4_320"),
        config=ASTRAL3Config(is_exact=False),
    )
    assert "-x" not in argv


def test_astral3_artifact_paths():
    out = Path("out/high_0.1_4_320")
    variant = runners.ASTRAL_VARIANT
    assert (
        runners.point_estimate_path(TreeInferenceMethod.PCH_ASTRAL3, out, "sim_0_1_1")
        == out / variant / "trees" / "sim_0_1_1.tree"
    )
    assert (
        runners.group_estimate_path(TreeInferenceMethod.PCH_ASTRAL3, out, "sim_0_1_1")
        is None
    )
    assert runners.consensus_method(TreeInferenceMethod.PCH_ASTRAL3) is None
    assert (
        runners.log_path(TreeInferenceMethod.PCH_ASTRAL3, out, "sim_0_1_1")
        == out / variant / "logs" / "sim_0_1_1.log"
    )


def test_missing_prerequisites_none_for_mp_and_ga():
    out = Path("out/high_0.1_4_320")
    assert (
        runners.missing_prerequisites(
            TreeInferenceMethod.MP, MP4Config(), out, "sim_0_1_1"
        )
        == []
    )
    assert (
        runners.missing_prerequisites(
            TreeInferenceMethod.GA, GAConfig(), out, "sim_0_1_1"
        )
        == []
    )


def test_missing_prerequisites_astral3_exact_is_empty():
    out = Path("out/high_0.1_4_320")
    assert (
        runners.missing_prerequisites(
            TreeInferenceMethod.PCH_ASTRAL3,
            ASTRAL3Config(is_exact=True),
            out,
            "sim_0_1_1",
        )
        == []
    )


def test_missing_prerequisites_astral3_heuristic_lists_absent_files(tmp_path: Path):
    missing = runners.missing_prerequisites(
        TreeInferenceMethod.PCH_ASTRAL3,
        ASTRAL3Config(is_exact=False),
        tmp_path,
        "sim_0_1_1",
    )
    assert missing == [
        tmp_path / "MP4" / "trees" / "sim_0_1_1.trees",
        tmp_path / "GA" / "trees1" / "sim_0_1_1.trees",
    ]


def test_missing_prerequisites_astral3_heuristic_empty_when_present(tmp_path: Path):
    for rel in ("MP4/trees/sim_0_1_1.trees", "GA/trees1/sim_0_1_1.trees"):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("(a,(b,c));\n")
    assert (
        runners.missing_prerequisites(
            TreeInferenceMethod.PCH_ASTRAL3,
            ASTRAL3Config(is_exact=False),
            tmp_path,
            "sim_0_1_1",
        )
        == []
    )


def test_unimplemented_method_raises():
    with pytest.raises(NotImplementedError):
        runners.build_argv(
            TreeInferenceMethod.PCH_WASTRAL,
            "x",
            Path("a.csv"),
            "a",
            Path("o"),
            MP4Config(),
        )
    with pytest.raises(NotImplementedError):
        runners.point_estimate_path(TreeInferenceMethod.PCH_WASTRAL, Path("o"), "a")
    with pytest.raises(NotImplementedError):
        runners.group_estimate_path(TreeInferenceMethod.PCH_WASTRAL, Path("o"), "a")
    with pytest.raises(NotImplementedError):
        runners.consensus_method(TreeInferenceMethod.PCH_WASTRAL)
    with pytest.raises(NotImplementedError):
        runners.log_path(TreeInferenceMethod.PCH_WASTRAL, Path("o"), "a")
