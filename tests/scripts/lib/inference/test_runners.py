from pathlib import Path

from scripts.lib.experiment import (
    ASTRAL3Config,
    GAConfig,
    MP4Config,
    WeightedASTRALConfig,
    WeightedTreeQMCConfig,
)
from scripts.lib.inference.inference import TreeInferenceMethod
from scripts.lib.inference.runners import ASTRAL_VARIANT, RUNNERS


def test_runners_cover_every_method():
    assert set(RUNNERS) == set(TreeInferenceMethod)


def test_build_mp4_argv():
    argv = RUNNERS[TreeInferenceMethod.MP].build_argv(
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
    runner = RUNNERS[TreeInferenceMethod.MP]
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


def test_build_ga_argv():
    argv = RUNNERS[TreeInferenceMethod.GA].build_argv(
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
    runner = RUNNERS[TreeInferenceMethod.GA]
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


def test_build_astral3_argv_exact():
    argv = RUNNERS[TreeInferenceMethod.PCH_ASTRAL3].build_argv(
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
    argv = RUNNERS[TreeInferenceMethod.PCH_ASTRAL3].build_argv(
        runid="abc123",
        input_csv=Path("data/sim_0_1_1.csv"),
        name="sim_0_1_1",
        output_dir=Path("out/high_0.1_4_320"),
        config=ASTRAL3Config(is_exact=False),
    )
    assert "-x" not in argv


def test_astral3_artifact_paths():
    out = Path("out/high_0.1_4_320")
    runner = RUNNERS[TreeInferenceMethod.PCH_ASTRAL3]
    assert (
        runner.point_estimate_path(out, "sim_0_1_1")
        == out / ASTRAL_VARIANT / "trees" / "sim_0_1_1.tree"
    )
    assert runner.group_estimate_path(out, "sim_0_1_1") is None
    assert runner.consensus_method() is None
    assert (
        runner.log_path(out, "sim_0_1_1")
        == out / ASTRAL_VARIANT / "logs" / "sim_0_1_1.log"
    )


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


def test_build_wastral_argv():
    argv = RUNNERS[TreeInferenceMethod.PCH_WASTRAL].build_argv(
        runid="abc123",
        input_csv=Path("data/sim_0_1_1.csv"),
        name="sim_0_1_1",
        output_dir=Path("out/high_0.1_4_320"),
        config=WeightedASTRALConfig(),
    )
    assert argv == [
        "bash",
        "scripts/sh/runWASTRAL.sh",
        "--runid",
        "abc123",
        "--input",
        "data/sim_0_1_1.csv",
        "--name",
        "sim_0_1_1",
        "--output",
        "out/high_0.1_4_320",
    ]


def test_build_tree_qmc_argv_has_norm():
    argv = RUNNERS[TreeInferenceMethod.PCH_W_TREE_QMC].build_argv(
        runid="abc123",
        input_csv=Path("data/sim_0_1_1.csv"),
        name="sim_0_1_1",
        output_dir=Path("out/high_0.1_4_320"),
        config=WeightedTreeQMCConfig(normalisation_strategy="n2"),
    )
    assert argv == [
        "bash",
        "scripts/sh/runTREEQMC.sh",
        "--runid",
        "abc123",
        "--input",
        "data/sim_0_1_1.csv",
        "--name",
        "sim_0_1_1",
        "--output",
        "out/high_0.1_4_320",
        "--norm",
        "2",
    ]


def test_wastral_point_estimate_path():
    out = Path("out/high_0.1_4_320")
    assert (
        RUNNERS[TreeInferenceMethod.PCH_WASTRAL].point_estimate_path(out, "sim_0_1_1")
        == out / "WASTRAL" / "trees" / "sim_0_1_1.tree"
    )


def test_tree_qmc_point_estimate_path():
    out = Path("out/high_0.1_4_320")
    assert (
        RUNNERS[TreeInferenceMethod.PCH_W_TREE_QMC].point_estimate_path(
            out, "sim_0_1_1"
        )
        == out / "TREEQMC" / "trees" / "sim_0_1_1.tree"
    )


def test_missing_prerequisites_empty_for_quartet_methods():
    out = Path("out/high_0.1_4_320")
    assert (
        RUNNERS[TreeInferenceMethod.PCH_WASTRAL].missing_prerequisites(
            WeightedASTRALConfig(), out, "sim_0_1_1"
        )
        == []
    )
    assert (
        RUNNERS[TreeInferenceMethod.PCH_W_TREE_QMC].missing_prerequisites(
            WeightedTreeQMCConfig(normalisation_strategy="n2"), out, "sim_0_1_1"
        )
        == []
    )
