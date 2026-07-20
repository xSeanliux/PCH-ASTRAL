from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from scripts.lib.experiment import WeightedTreeQMCConfig
from scripts.lib.inference.inference import ConsensusMethod, TreeInferenceMethod
from scripts.lib.pch import PCH_W


class WTreeQmcRunner:
    # runWTREEQMC.sh generates quartets via PCH_W (scripts.lib.pch --format qfm),
    # then infers a tree with weighted TREE-QMC.
    SCHEME = PCH_W
    # PCH_W (quartet scheme) + W_TREE_QMC (weighted TREE-QMC); cf. PCH_W_ASTRAL3.
    VARIANT = f"{SCHEME.__name__}_W_TREE_QMC"  # -> "PCH_W_W_TREE_QMC"

    @staticmethod
    def dependencies(config: BaseModel) -> list[TreeInferenceMethod]:
        # Standalone: builds its own quartets, consumes no upstream tree sets.
        return []

    @staticmethod
    def build_argv(
        runid: str, input_csv: Path, name: str, output_dir: Path, config: BaseModel
    ) -> list[str]:
        # -V is the single source of truth for the output folder name.
        assert isinstance(config, WeightedTreeQMCConfig)
        return [
            "bash",
            "scripts/sh/runWTREEQMC.sh",
            "-H",
            runid,
            "-i",
            str(input_csv),
            "-o",
            str(output_dir),
            "-V",
            WTreeQmcRunner.VARIANT,
            "-n",
            name,
            "-N",
            str(config.normalisation_strategy.value),
        ]

    @staticmethod
    def point_estimate_path(output_dir: Path, name: str) -> Path:
        return output_dir / WTreeQmcRunner.VARIANT / "trees" / f"{name}.tree"

    @staticmethod
    def group_estimate_path(output_dir: Path, name: str) -> Optional[Path]:
        return None

    @staticmethod
    def consensus_method() -> Optional[ConsensusMethod]:
        return None

    @staticmethod
    def log_path(output_dir: Path, name: str) -> Path:
        return output_dir / WTreeQmcRunner.VARIANT / "logs" / f"{name}.log"
