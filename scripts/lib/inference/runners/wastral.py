from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from scripts.lib.experiment import WeightedASTRALConfig
from scripts.lib.inference.inference import ConsensusMethod, TreeInferenceMethod
from scripts.lib.pch import PCH_W


class WASTRALRunner:
    # runWASTRAL.sh generates quartets via PCH_W (scripts.lib.pch --format wastral),
    # then infers a tree with weighted ASTRAL. No config (like MP4).
    SCHEME = PCH_W
    # PCH_W (quartet scheme) + WASTRAL; cf. PCH_W_W_TREE_QMC.
    VARIANT = f"{SCHEME.__name__}_WASTRAL"  # -> "PCH_W_WASTRAL"

    @staticmethod
    def dependencies(config: BaseModel) -> list[TreeInferenceMethod]:
        # Standalone: builds its own quartets, consumes no upstream tree sets.
        return []

    @staticmethod
    def build_argv(
        runid: str, input_csv: Path, name: str, output_dir: Path, config: BaseModel
    ) -> list[str]:
        # -V is the single source of truth for the output folder name.
        assert isinstance(config, WeightedASTRALConfig)
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
