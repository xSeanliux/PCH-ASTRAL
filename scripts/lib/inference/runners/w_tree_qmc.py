from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from scripts.lib.inference.runners.base import Runner
from scripts.lib.model.methods import TreeInferenceMethod
from scripts.lib.pch import PCH_W

if TYPE_CHECKING:
    from scripts.lib.experiment import WeightedTreeQMCConfig  # noqa: F401  (used in the quoted base)


@dataclass(frozen=True)
class WTreeQmcRunner(Runner["WeightedTreeQMCConfig"]):
    # runWTREEQMC.sh generates quartets via PCH_W (scripts.lib.pch --format qfm),
    # then infers a tree with weighted TREE-QMC. Standalone: no upstream tree sets.
    SCHEME = PCH_W
    # PCH_W (quartet scheme) + W_TREE_QMC (weighted TREE-QMC); cf. PCH_W_ASTRAL3.
    VARIANT = f"{SCHEME.__name__}_W_TREE_QMC"  # -> "PCH_W_W_TREE_QMC"

    @property
    def method(self) -> TreeInferenceMethod:
        return TreeInferenceMethod.PCH_W_TREE_QMC

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
    def get_point_estimate_path(output_dir: Path, name: str) -> Path:
        return output_dir / WTreeQmcRunner.VARIANT / "trees" / f"{name}.tree"

    @staticmethod
    def get_log_path(output_dir: Path, name: str) -> Path:
        return output_dir / WTreeQmcRunner.VARIANT / "logs" / f"{name}.log"
