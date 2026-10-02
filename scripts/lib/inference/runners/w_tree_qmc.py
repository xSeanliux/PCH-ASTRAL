from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from scripts.lib.model.methods import (
    ConsensusMethod,
    InferenceMethod,
    TreeInferenceMethod,
)
from scripts.lib.pch import PCH_W

if TYPE_CHECKING:
    from scripts.lib.experiment import WeightedTreeQMCConfig


@dataclass(frozen=True)
class WTreeQmcRunner:
    # runWTREEQMC.sh generates quartets via PCH_W (scripts.lib.pch --format qfm),
    # then infers a tree with weighted TREE-QMC.
    SCHEME = PCH_W
    # PCH_W (quartet scheme) + W_TREE_QMC (weighted TREE-QMC); cf. PCH_W_ASTRAL3.
    VARIANT = f"{SCHEME.__name__}_W_TREE_QMC"  # -> "PCH_W_W_TREE_QMC"

    config: "WeightedTreeQMCConfig"
    method: InferenceMethod = TreeInferenceMethod.PCH_W_TREE_QMC
    suffix: str | None = None

    def dependencies(self) -> list[InferenceMethod]:
        # Standalone: builds its own quartets, consumes no upstream tree sets.
        return []

    def build_argv(
        self, runid: str, input_csv: Path, name: str, output_dir: Path
    ) -> list[str]:
        # -V is the single source of truth for the output folder name.
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
            str(self.config.normalisation_strategy.value),
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
