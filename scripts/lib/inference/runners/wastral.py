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
    from scripts.lib.experiment import WeightedASTRALConfig


@dataclass(frozen=True)
class WASTRALRunner:
    # runWASTRAL.sh generates quartets via PCH_W (scripts.lib.pch --format wastral),
    # then infers a tree with weighted ASTRAL. No config (like MP4).
    SCHEME = PCH_W
    # PCH_W (quartet scheme) + WASTRAL; cf. PCH_W_W_TREE_QMC.
    VARIANT = f"{SCHEME.__name__}_WASTRAL"  # -> "PCH_W_WASTRAL"

    config: "WeightedASTRALConfig"
    suffix: str | None = None

    @property
    def method(self) -> TreeInferenceMethod:
        return TreeInferenceMethod.PCH_WASTRAL

    def dependencies(self) -> list[InferenceMethod]:
        # Standalone: builds its own quartets, consumes no upstream tree sets.
        return []

    def build_argv(
        self, runid: str, input_csv: Path, name: str, output_dir: Path
    ) -> list[str]:
        # -V is the single source of truth for the output folder name.
        return [
            "bash",
            "scripts/sh/runWASTRAL.sh",
            "-H",
            runid,
            "-i",
            str(input_csv),
            "-o",
            str(output_dir),
            "-V",
            WASTRALRunner.VARIANT,
            "-n",
            name,
        ]

    @staticmethod
    def point_estimate_path(output_dir: Path, name: str) -> Path:
        return output_dir / WASTRALRunner.VARIANT / "trees" / f"{name}.tree"

    @staticmethod
    def group_estimate_path(output_dir: Path, name: str) -> Optional[Path]:
        return None

    @staticmethod
    def consensus_method() -> Optional[ConsensusMethod]:
        return None

    @staticmethod
    def log_path(output_dir: Path, name: str) -> Path:
        return output_dir / WASTRALRunner.VARIANT / "logs" / f"{name}.log"
