from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from scripts.lib.inference.runners.base import Runner
from scripts.lib.model.methods import TreeInferenceMethod
from scripts.lib.pch import PCH_W

if TYPE_CHECKING:
    from scripts.lib.experiment import WeightedASTRALConfig  # noqa: F401  (used in the quoted base)


@dataclass(frozen=True)
class WASTRALRunner(Runner["WeightedASTRALConfig"]):
    # runWASTRAL.sh generates quartets via PCH_W (scripts.lib.pch --format wastral),
    # then infers a tree with weighted ASTRAL. Standalone: no upstream tree sets.
    SCHEME = PCH_W
    # PCH_W (quartet scheme) + WASTRAL; cf. PCH_W_W_TREE_QMC.
    VARIANT = f"{SCHEME.__name__}_WASTRAL"  # -> "PCH_W_WASTRAL"

    @property
    def method(self) -> TreeInferenceMethod:
        return TreeInferenceMethod.PCH_WASTRAL

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
    def get_point_estimate_path(output_dir: Path, name: str) -> Path:
        return output_dir / WASTRALRunner.VARIANT / "trees" / f"{name}.tree"

    @staticmethod
    def get_log_path(output_dir: Path, name: str) -> Path:
        return output_dir / WASTRALRunner.VARIANT / "logs" / f"{name}.log"
