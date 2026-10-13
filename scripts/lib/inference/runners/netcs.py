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
    from scripts.lib.experiment import NetcsConfig  # noqa: F401  (used in the quoted base)


@dataclass(frozen=True)
class NetcsRunner(Runner["NetcsConfig"]):
    """NetCS: PCH-W quartets and TOB-QMC's tree of blobs in, one level-1 network out."""

    @property
    def method(self) -> NetworkInferenceMethod:
        """`netcs`."""
        return NetworkInferenceMethod.NETCS

    def get_dependencies(self) -> list[InferenceMethod]:
        """The tree of blobs NetCS resolves."""
        return [TreeInferenceMethod.TOB_QMC]

    def build_argv(
        self, runid: str, input_csv: Path, name: str, output_dir: Path
    ) -> list[str]:
        """The `runNETCS.sh` command; arguments as `runTOBQMC.sh`."""
        return [
            "bash",
            "scripts/sh/runNETCS.sh",
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
        """The network, eNewick, as NetCS wrote it."""
        return output_dir / "NETCS" / "networks" / f"{name}.net"

    @staticmethod
    def get_log_path(output_dir: Path, name: str) -> Path:
        """The run log; holds NetCS's rooting verdict."""
        return output_dir / "NETCS" / "logs" / f"{name}.log"
