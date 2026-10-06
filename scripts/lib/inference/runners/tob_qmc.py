from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from scripts.lib.inference.runners.base import Runner
from scripts.lib.model.methods import NetworkInferenceMethod

if TYPE_CHECKING:
    from scripts.lib.experiment import TobQmcConfig  # noqa: F401  (used in the quoted base)


@dataclass(frozen=True)
class TobQmcRunner(Runner["TobQmcConfig"]):
    """TOB-QMC: PCH-W quartets in, the network's tree of blobs out (one newick)."""

    @property
    def method(self) -> NetworkInferenceMethod:
        return NetworkInferenceMethod.TOB_QMC

    def build_argv(
        self, runid: str, input_csv: Path, name: str, output_dir: Path
    ) -> list[str]:
        return [
            "bash",
            "scripts/sh/runTOBQMC.sh",
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
        return output_dir / "TOB_QMC" / "trees" / f"{name}.tree"

    @staticmethod
    def get_log_path(output_dir: Path, name: str) -> Path:
        return output_dir / "TOB_QMC" / "logs" / f"{name}.log"
