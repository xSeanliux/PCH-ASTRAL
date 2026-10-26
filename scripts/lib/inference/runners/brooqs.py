from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

from scripts.lib.inference.runners.base import get_quartets_path, write_quartets
from scripts.lib.inference.runners.tob_qmc import TreeOfBlobsConsumerRunner
from scripts.lib.pch import print_quartets_for_astral3
from scripts.lib.model.methods import NetworkInferenceMethod

if TYPE_CHECKING:
    from scripts.lib.experiment import BrooqsConfig  # noqa: F401  (used in the quoted base)


@dataclass(frozen=True)
class BrooqsRunner(TreeOfBlobsConsumerRunner["BrooqsConfig"]):
    """BROOQS: expands TOB-QMC's tree of blobs into a level-1 network (eNewick)."""

    @property
    def method(self) -> NetworkInferenceMethod:
        return NetworkInferenceMethod.BROOQS

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
            "--quartets",
            str(get_quartets_path(runid)),
            "--tree-of-blobs",
            str(self.get_tree_of_blobs_path(input_csv, output_dir)),
        ]

    def execute(
        self, runid: str, input_csv: Path, name: str, output_dir: Path, log_file: TextIO
    ) -> int:
        """Write the quartets, then run BROOQS.

        :returns: the exit code.
        """
        write_quartets(self.config, input_csv, runid, print_quartets_for_astral3)
        return super().execute(runid, input_csv, name, output_dir, log_file)

    @staticmethod
    def get_point_estimate_path(output_dir: Path, name: str) -> Path:
        """The network, eNewick, topology only."""
        return output_dir / "BROOQS" / "networks" / f"{name}.net"

    @staticmethod
    def get_log_path(output_dir: Path, name: str) -> Path:
        return output_dir / "BROOQS" / "logs" / f"{name}.log"
