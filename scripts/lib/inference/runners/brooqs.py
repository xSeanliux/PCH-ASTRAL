from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

from scripts.lib.inference.runners.base import (
    Runner,
    get_quartet_suffix,
    get_quartets_path,
    write_quartets,
)
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

    @property
    def suffix(self) -> str | None:
        """The quartet strategy unless PCH_W."""
        return get_quartet_suffix(self.config)

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
        ]

    def execute(
        self, runid: str, input_csv: Path, name: str, output_dir: Path, log_file: TextIO
    ) -> int:
        """Write the quartets, then run BROOQS.

        :returns: the exit code.
        """
        write_quartets(self.config, input_csv, runid)
        return super().execute(runid, input_csv, name, output_dir, log_file)

    @staticmethod
    def get_point_estimate_path(output_dir: Path, name: str) -> Path:
        """The network, eNewick, topology only."""
        return output_dir / "BROOQS" / "networks" / f"{name}.net"

    @staticmethod
    def get_log_path(output_dir: Path, name: str) -> Path:
        return output_dir / "BROOQS" / "logs" / f"{name}.log"
