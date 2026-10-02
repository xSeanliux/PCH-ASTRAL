from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from scripts.lib.model.guide_tree import GuideTree
from scripts.lib.model.methods import InferenceMethod, NetworkInferenceMethod

if TYPE_CHECKING:
    from scripts.lib.experiment import CamusConfig


@dataclass(frozen=True)
class CamusRunner:
    """CAMUS level-1 network inference: one guide tree in, one network family out."""

    config: "CamusConfig"  # the single-guide config; what config_hash hashes

    @property
    def method(self) -> NetworkInferenceMethod:
        return NetworkInferenceMethod.CAMUS

    @property
    def guide(self) -> GuideTree:
        (guide,) = self.config.guide_trees
        return guide

    @property
    def suffix(self) -> str:
        return self.guide.value

    def dependencies(self) -> list[InferenceMethod]:
        return [] if self.guide.dependency is None else [self.guide.dependency]

    def build_argv(
        self, runid: str, input_csv: Path, name: str, output_dir: Path
    ) -> list[str]:
        return [
            "bash",
            "scripts/sh/runCAMUS.sh",
            "--runid",
            runid,
            "--input",
            str(input_csv),
            "--name",
            name,
            "--output",
            str(output_dir),
            "--guide-tree",
            self.guide.value,
        ]

    @staticmethod
    def family_path(output_dir: Path, name: str) -> Path:
        # CAMUS writes `<prefix>.csv`, one row per k; runCAMUS.sh sets -o to this stem.
        return output_dir / "CAMUS" / "networks" / f"{name}.csv"

    @staticmethod
    def log_path(output_dir: Path, name: str) -> Path:
        return output_dir / "CAMUS" / "logs" / f"{name}.log"
