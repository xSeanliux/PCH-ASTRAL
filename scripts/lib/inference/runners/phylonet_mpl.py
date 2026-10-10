from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from scripts.lib.inference.runners.base import Runner
from scripts.lib.model.methods import (
    InferenceMethod,
    NetworkInferenceMethod,
    TreeInferenceMethod,
)

if TYPE_CHECKING:
    from scripts.lib.experiment import PhyloNetMPLConfig  # noqa: F401  (used in the quoted base)


@dataclass(frozen=True)
class PhyloNetMPLRunner(Runner["PhyloNetMPLConfig"]):
    """PhyloNet-MPL(FT): rooted PCH-W quartets plus the fixed pch_wastral tree in,
    networks out."""

    @property
    def method(self) -> NetworkInferenceMethod:
        return NetworkInferenceMethod.PHYLONET_MPL

    def get_dependencies(self) -> list[InferenceMethod]:
        """The start tree's method."""
        return [TreeInferenceMethod.PCH_WASTRAL]

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
