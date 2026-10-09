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
    from scripts.lib.experiment import SnaqConfig  # noqa: F401  (used in the quoted base)


@dataclass(frozen=True)
class SnaqRunner(Runner["SnaqConfig"]):
    """SNaQ level-1 network inference from PCH-W quartet CFs; one network out."""

    @property
    def method(self) -> NetworkInferenceMethod:
        return NetworkInferenceMethod.SNAQ

    def get_dependencies(self) -> list[InferenceMethod]:
        """pch_wastral: its tree is SNaQ's start tree."""
        return [TreeInferenceMethod.PCH_WASTRAL]

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
        ]

    @staticmethod
    def get_point_estimate_path(output_dir: Path, name: str) -> Path:
        """The best network, Rich newick; `run_snaq.jl` writes it."""
        return output_dir / "SNAQ" / "networks" / f"{name}.net"

    @staticmethod
    def get_group_estimate_path(output_dir: Path, name: str) -> Path:
        """Family CSV: the best network, then SNaQ's alternatives, with -loglik."""
        return output_dir / "SNAQ" / "networks" / f"{name}.family.csv"

    @staticmethod
    def get_log_path(output_dir: Path, name: str) -> Path:
        return output_dir / "SNAQ" / "logs" / f"{name}.log"
