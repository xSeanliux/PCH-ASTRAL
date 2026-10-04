from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from scripts.lib.inference.runners.base import Runner
from scripts.lib.model.guide_tree import GuideTree
from scripts.lib.model.methods import (
    InferenceMethod,
    NetworkInferenceMethod,
    TreeInferenceMethod,
)

if TYPE_CHECKING:
    from scripts.lib.experiment import CamusConfig  # noqa: F401  (used in the quoted base)


@dataclass(frozen=True)
class CamusRunner(Runner["CamusConfig"]):
    """CAMUS level-1 network inference: one guide tree in, one network family out.

    `config` is the single-guide config.
    """

    @property
    def method(self) -> NetworkInferenceMethod:
        return NetworkInferenceMethod.CAMUS

    @property
    def guide(self) -> GuideTree:
        (guide,) = self.config.guide_trees
        return guide

    @property
    def suffix(self) -> str:
        return str(self.guide)

    def get_dependencies(self) -> list[InferenceMethod]:
        guide = self.guide
        return [guide] if isinstance(guide, TreeInferenceMethod) else []

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
            str(self.guide),
        ]

    @staticmethod
    def get_point_estimate_path(output_dir: Path, name: str) -> None:
        # ponytail: no rule for picking a k yet; add one when analysis picks it
        return None

    @staticmethod
    def get_group_estimate_path(output_dir: Path, name: str) -> Path:
        # CAMUS writes `<prefix>.csv`, one row per k; runCAMUS.sh sets -o to this stem.
        return output_dir / "CAMUS" / "networks" / f"{name}.csv"

    @staticmethod
    def get_log_path(output_dir: Path, name: str) -> Path:
        return output_dir / "CAMUS" / "logs" / f"{name}.log"
