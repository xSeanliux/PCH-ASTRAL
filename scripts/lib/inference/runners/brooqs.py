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
    from scripts.lib.experiment import BrooqsConfig  # noqa: F401  (used in the quoted base)


@dataclass(frozen=True)
class BrooqsRunner(Runner["BrooqsConfig"]):
    """BROOQS: expands TOB-QMC's tree of blobs into a level-1 network (eNewick)."""

    @property
    def method(self) -> NetworkInferenceMethod:
        return NetworkInferenceMethod.BROOQS

    def get_dependencies(self) -> list[InferenceMethod]:
        """The tree of blobs BROOQS expands."""
        return [TreeInferenceMethod.TOB_QMC]

    def build_argv(
        self, runid: str, input_csv: Path, name: str, output_dir: Path
    ) -> list[str]:
        return [
            "bash",
            "scripts/sh/runBROOQS.sh",
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
        """The network, eNewick, topology only."""
        return output_dir / "BROOQS" / "networks" / f"{name}.net"

    @staticmethod
    def get_log_path(output_dir: Path, name: str) -> Path:
        return output_dir / "BROOQS" / "logs" / f"{name}.log"
