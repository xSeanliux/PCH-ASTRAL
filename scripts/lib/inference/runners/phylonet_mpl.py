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
    from scripts.lib.experiment import PhyloNetMPLConfig  # noqa: F401  (used in the quoted base)


@dataclass(frozen=True)
class PhyloNetMPLRunner(Runner["PhyloNetMPLConfig"]):
    """PhyloNet-MPL(FT): rooted PCH-W quartets plus the fixed guide tree in,
    networks out.

    `config` is the single-guide config.
    """

    @property
    def method(self) -> NetworkInferenceMethod:
        return NetworkInferenceMethod.PHYLONET_MPL

    @property
    def guide(self) -> GuideTree:
        """The one fixed tree this run uses; `get_runners` splits the set."""
        (guide,) = self.config.guide_trees
        return guide

    @property
    def suffix(self) -> str:
        """The guide's name, so runs on one dataset don't collide."""
        return str(self.guide)

    def get_dependencies(self) -> list[InferenceMethod]:
        """The method that produces the fixed tree; none for `true_tree`."""
        guide = self.guide
        return [guide] if isinstance(guide, TreeInferenceMethod) else []

    def build_argv(
        self, runid: str, input_csv: Path, name: str, output_dir: Path
    ) -> list[str]:
        return [
            "bash",
            "scripts/sh/runPhyloNetMPL.sh",
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
        """The best network, Rich newick as PhyloNet wrote it."""
        return output_dir / "PHYLONET_MPL" / "networks" / f"{name}.net"

    @staticmethod
    def get_group_estimate_path(output_dir: Path, name: str) -> Path:
        """Family CSV: PhyloNet's networks, best first, with log pseudo-likelihoods."""
        return output_dir / "PHYLONET_MPL" / "networks" / f"{name}.family.csv"

    @staticmethod
    def get_log_path(output_dir: Path, name: str) -> Path:
        return output_dir / "PHYLONET_MPL" / "logs" / f"{name}.log"
