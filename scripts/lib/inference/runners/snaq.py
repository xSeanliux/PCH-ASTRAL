from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from scripts.lib.inference.runners.base import Runner
from scripts.lib.model.guide_tree import GuideTree
from scripts.lib.model.methods import (
    InferenceMethod,
    NetworkInferenceMethod,
    TreeInferenceMethod,
)

if TYPE_CHECKING:
    from scripts.lib.experiment import SnaqConfig  # noqa: F401  (used in the quoted base)


@dataclass(frozen=True)
class SnaqRunner(Runner["SnaqConfig"]):
    """SNaQ level-1 network inference from PCH-W quartet CFs; one network out.

    `config` is the single-guide config; the guide is SNaQ's start tree.
    """

    # No network consistent with the outgroup: no .net, the family still recorded.
    is_point_estimate_optional: ClassVar[bool] = True

    @property
    def method(self) -> NetworkInferenceMethod:
        return NetworkInferenceMethod.SNAQ

    @property
    def guide(self) -> GuideTree:
        """The one start tree this run uses; `get_runners` splits the set."""
        (guide,) = self.config.guide_trees
        return guide

    @property
    def suffix(self) -> str:
        """The guide's name, so runs on one dataset don't collide."""
        return str(self.guide)

    def get_dependencies(self) -> list[InferenceMethod]:
        """The method that produces the start tree; none for `true_tree`."""
        guide = self.guide
        return [guide] if isinstance(guide, TreeInferenceMethod) else []

    def build_argv(
        self, runid: str, input_csv: Path, name: str, output_dir: Path
    ) -> list[str]:
        return [
            "bash",
            "scripts/sh/runSNAQ.sh",
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
    def get_point_estimate_path(output_dir: Path, name: str) -> Path:
        """The chosen network, Rich newick; `run_snaq.jl` writes it if any."""
        return output_dir / "SNAQ" / "networks" / f"{name}.net"

    @staticmethod
    def get_group_estimate_path(output_dir: Path, name: str) -> Path:
        """Family CSV: the best network, then SNaQ's alternatives, with -loglik."""
        return output_dir / "SNAQ" / "networks" / f"{name}.family.csv"

    @staticmethod
    def get_log_path(output_dir: Path, name: str) -> Path:
        return output_dir / "SNAQ" / "logs" / f"{name}.log"
