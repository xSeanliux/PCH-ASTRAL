from pathlib import Path

import pytest

from scripts.lib.experiment import ASTRAL3Config, GAConfig, MP4Config
from scripts.lib.inference import runners
from scripts.lib.inference.runners import METHOD_TO_RUNNER_CLASS
from scripts.lib.model.methods import ConsensusMethod, TreeInferenceMethod


def test_mp4_runner_build_argv():
    runner = METHOD_TO_RUNNER_CLASS[TreeInferenceMethod.MP](config=MP4Config())
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
    runner_cls = METHOD_TO_RUNNER_CLASS[TreeInferenceMethod.MP]
    out = Path("out/high_0.1_4_320")
    assert (
        runner_cls.get_point_estimate_path(out, "sim_0_1_1")
        == out / "MP4" / "trees" / "sim_0_1_1-maj.tree"
    )
    assert (
        runner_cls.get_group_estimate_path(out, "sim_0_1_1")
        == out / "MP4" / "trees" / "sim_0_1_1.trees"
    )
    assert runner_cls.get_consensus_method() == ConsensusMethod.MAJORITY
    assert (
        runner_cls.get_log_path(out, "sim_0_1_1")
        == out / "MP4" / "logs" / "sim_0_1_1.log"
    )


def test_ga_runner_build_argv():
    runner = METHOD_TO_RUNNER_CLASS[TreeInferenceMethod.GA](config=GAConfig())
    argv = runner.build_argv(
        runid="abc123",
        input_csv=Path("data/sim_0_1_1.csv"),
        name="sim_0_1_1",
        output_dir=Path("out/high_0.1_4_320"),
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
    runner_cls = METHOD_TO_RUNNER_CLASS[TreeInferenceMethod.GA]
    out = Path("out/high_0.1_4_320")
    assert (
        runner_cls.get_point_estimate_path(out, "sim_0_1_1")
        == out / "GA" / "trees" / "sim_0_1_1.tree"
    )
    assert (
        runner_cls.get_group_estimate_path(out, "sim_0_1_1")
        == out / "GA" / "trees1" / "sim_0_1_1.trees"
    )
    assert runner_cls.get_consensus_method() == ConsensusMethod.MCC
    assert (
        runner_cls.get_log_path(out, "sim_0_1_1")
        == out / "GA" / "logs" / "sim_0_1_1.log"
    )


def _astral3_runner(config: ASTRAL3Config):
    return METHOD_TO_RUNNER_CLASS[TreeInferenceMethod.PCH_ASTRAL3](config=config)


def test_astral3_runner_build_argv_exact():
    argv = _astral3_runner(ASTRAL3Config(is_exact=True)).build_argv(
        runid="abc123",
        input_csv=Path("data/sim_0_1_1.csv"),
        name="sim_0_1_1",
        output_dir=Path("out/high_0.1_4_320"),
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
        "PCH_W_ASTRAL3",
        "-n",
        "sim_0_1_1",
        "-x",
    ]


def test_astral3_runner_build_argv_heuristic_has_no_x():
    argv = _astral3_runner(ASTRAL3Config(is_exact=False)).build_argv(
        runid="abc123",
        input_csv=Path("data/sim_0_1_1.csv"),
        name="sim_0_1_1",
        output_dir=Path("out/high_0.1_4_320"),
    )
    assert "-x" not in argv


def _astral3_argv(config: ASTRAL3Config) -> list[str]:
    return _astral3_runner(config).build_argv(
        runid="abc123",
        input_csv=Path("data/sim_0_1_1.csv"),
        name="sim_0_1_1",
        output_dir=Path("out/high_0.1_4_320"),
    )


def test_astral3_runner_build_argv_default_sources_mp4_ga():
    argv = _astral3_argv(ASTRAL3Config(is_exact=False))
    assert argv[argv.index("-S") + 1] == "mp4,ga"


def test_astral3_runner_build_argv_ga_only_source():
    argv = _astral3_argv(
        ASTRAL3Config(is_exact=False, bipartition_strategies=["ga_trees"])
    )
    assert argv[argv.index("-S") + 1] == "ga"


def test_astral3_runner_build_argv_exact_has_no_sources():
    assert "-S" not in _astral3_argv(ASTRAL3Config(is_exact=True))


def test_astral3_runner_binary_character_not_implemented():
    with pytest.raises(NotImplementedError):
        _astral3_argv(
            ASTRAL3Config(is_exact=False, bipartition_strategies=["binary_character"])
        )


def test_astral3_runner_artifact_paths():
    runner_cls = METHOD_TO_RUNNER_CLASS[TreeInferenceMethod.PCH_ASTRAL3]
    out = Path("out/high_0.1_4_320")
    variant = runners.ASTRAL3Runner.VARIANT
    assert (
        runner_cls.get_point_estimate_path(out, "sim_0_1_1")
        == out / variant / "trees" / "sim_0_1_1.tree"
    )
    assert runner_cls.get_group_estimate_path(out, "sim_0_1_1") is None
    assert runner_cls.get_consensus_method() is None
    assert (
        runner_cls.get_log_path(out, "sim_0_1_1")
        == out / variant / "logs" / "sim_0_1_1.log"
    )


def test_dependencies_mp_and_ga_are_empty():
    assert (
        METHOD_TO_RUNNER_CLASS[TreeInferenceMethod.MP](
            config=MP4Config()
        ).get_dependencies()
        == []
    )
    assert (
        METHOD_TO_RUNNER_CLASS[TreeInferenceMethod.GA](
            config=GAConfig()
        ).get_dependencies()
        == []
    )


def test_dependencies_astral3_exact_is_empty():
    assert _astral3_runner(ASTRAL3Config(is_exact=True)).get_dependencies() == []


def test_dependencies_astral3_heuristic_default_is_mp_ga():
    assert _astral3_runner(ASTRAL3Config(is_exact=False)).get_dependencies() == [
        TreeInferenceMethod.MP,
        TreeInferenceMethod.GA,
    ]


def test_dependencies_astral3_ga_only():
    assert _astral3_runner(
        ASTRAL3Config(is_exact=False, bipartition_strategies=["ga_trees"])
    ).get_dependencies() == [TreeInferenceMethod.GA]


def test_registry_has_wired_methods():
    assert TreeInferenceMethod.MP in METHOD_TO_RUNNER_CLASS
    assert TreeInferenceMethod.GA in METHOD_TO_RUNNER_CLASS
    assert TreeInferenceMethod.PCH_ASTRAL3 in METHOD_TO_RUNNER_CLASS
    assert TreeInferenceMethod.PCH_W_TREE_QMC in METHOD_TO_RUNNER_CLASS
    assert TreeInferenceMethod.PCH_WASTRAL in METHOD_TO_RUNNER_CLASS
