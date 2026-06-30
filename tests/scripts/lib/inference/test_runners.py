from pathlib import Path

from scripts.lib.experiment import ASTRAL3Config, GAConfig, MP4Config
from scripts.lib.inference import runners
from scripts.lib.inference.runners import RUNNERS
from scripts.lib.inference.inference import TreeInferenceMethod


def test_mp4_runner_build_argv():
    runner = RUNNERS[TreeInferenceMethod.MP]
    argv = runner.build_argv(
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


def test_ga_runner_build_argv():
    runner = RUNNERS[TreeInferenceMethod.GA]
    argv = runner.build_argv(
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


def test_ga_runner_artifact_paths():
    runner = RUNNERS[TreeInferenceMethod.GA]
    out = Path("out/high_0.1_4_320")
    assert (
        runner.point_estimate_path(out, "sim_0_1_1")
        == out / "GA" / "trees" / "sim_0_1_1.tree"
    )
    assert (
        runner.group_estimate_path(out, "sim_0_1_1")
        == out / "GA" / "trees1" / "sim_0_1_1.trees"
    )
    assert runner.consensus_method() == "mcc"
    assert runner.log_path(out, "sim_0_1_1") == out / "GA" / "logs" / "sim_0_1_1.log"


def test_astral3_runner_build_argv_exact():
    runner = RUNNERS[TreeInferenceMethod.PCH_ASTRAL3]
    argv = runner.build_argv(
        runid="abc123",
        input_csv=Path("data/sim_0_1_1.csv"),
        name="sim_0_1_1",
        output_dir=Path("out/high_0.1_4_320"),
        config=ASTRAL3Config(is_exact=True),
    )
    assert argv == [
        "bash",
        "scripts/sh/runASTRAL3.sh",
        "-H",
        "abc123",
        "-i",
        "data/sim_0_1_1.csv",
        "-o",
        "out/high_0.1_4_320",
        "-V",
        "PCH_ASTRAL_3(11,5)",
        "-n",
        "sim_0_1_1",
        "-x",
    ]


def test_astral3_runner_build_argv_heuristic_has_no_x():
    runner = RUNNERS[TreeInferenceMethod.PCH_ASTRAL3]
    argv = runner.build_argv(
        runid="abc123",
        input_csv=Path("data/sim_0_1_1.csv"),
        name="sim_0_1_1",
        output_dir=Path("out/high_0.1_4_320"),
        config=ASTRAL3Config(is_exact=False),
    )
    assert "-x" not in argv


def test_astral3_runner_artifact_paths():
    runner = RUNNERS[TreeInferenceMethod.PCH_ASTRAL3]
    out = Path("out/high_0.1_4_320")
    variant = runners.ASTRAL_VARIANT
    assert (
        runner.point_estimate_path(out, "sim_0_1_1")
        == out / variant / "trees" / "sim_0_1_1.tree"
    )
    assert runner.group_estimate_path(out, "sim_0_1_1") is None
    assert runner.consensus_method() is None
    assert runner.log_path(out, "sim_0_1_1") == out / variant / "logs" / "sim_0_1_1.log"


def test_missing_prerequisites_none_for_mp_and_ga():
    out = Path("out/high_0.1_4_320")
    assert (
        RUNNERS[TreeInferenceMethod.MP].missing_prerequisites(
            MP4Config(), out, "sim_0_1_1"
        )
        == []
    )
    assert (
        RUNNERS[TreeInferenceMethod.GA].missing_prerequisites(
            GAConfig(), out, "sim_0_1_1"
        )
        == []
    )


def test_missing_prerequisites_astral3_exact_is_empty():
    out = Path("out/high_0.1_4_320")
    assert (
        RUNNERS[TreeInferenceMethod.PCH_ASTRAL3].missing_prerequisites(
            ASTRAL3Config(is_exact=True), out, "sim_0_1_1"
        )
        == []
    )


def test_missing_prerequisites_astral3_heuristic_lists_absent_files(tmp_path: Path):
    missing = RUNNERS[TreeInferenceMethod.PCH_ASTRAL3].missing_prerequisites(
        ASTRAL3Config(is_exact=False), tmp_path, "sim_0_1_1"
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
        RUNNERS[TreeInferenceMethod.PCH_ASTRAL3].missing_prerequisites(
            ASTRAL3Config(is_exact=False), tmp_path, "sim_0_1_1"
        )
        == []
    )


def test_registry_has_wired_methods():
    # M3 wires MP4/GA/ASTRAL3; later milestones add wASTRAL/TREE-QMC.
    assert TreeInferenceMethod.MP in RUNNERS
    assert TreeInferenceMethod.GA in RUNNERS
    assert TreeInferenceMethod.PCH_ASTRAL3 in RUNNERS
    assert TreeInferenceMethod.PCH_WASTRAL not in RUNNERS
