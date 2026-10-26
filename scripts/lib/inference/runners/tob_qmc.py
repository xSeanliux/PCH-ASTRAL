from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

from scripts.lib.inference.runners.base import (
    Runner,
    get_quartet_suffix,
    get_quartets_path,
    write_quartets,
)
from scripts.lib.pch import print_quartets_for_astral3
from scripts.lib.model.methods import TreeInferenceMethod

if TYPE_CHECKING:
    from scripts.lib.experiment import TobQmcConfig  # noqa: F401  (used in the quoted base)


@dataclass(frozen=True)
class TobQmcRunner(Runner["TobQmcConfig"]):
    """TOB-QMC: quartets in, the network's tree of blobs out (one newick)."""

    @property
    def method(self) -> TreeInferenceMethod:
        return TreeInferenceMethod.TOB_QMC

    @property
    def suffix(self) -> str | None:
        """The quartet strategy unless PCH_W."""
        return get_quartet_suffix(self.config)

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
            "--quartets",
            str(get_quartets_path(runid)),
            "--alpha",
            str(self.config.alpha),
            *(["--3f1a"] if self.config.three_fix_one_alter else []),
        ]

    def execute(
        self, runid: str, input_csv: Path, name: str, output_dir: Path, log_file: TextIO
    ) -> int:
        """Write the quartets, then run TOB-QMC.

        :returns: the exit code.
        """
        write_quartets(self.config, input_csv, runid, print_quartets_for_astral3)
        return super().execute(runid, input_csv, name, output_dir, log_file)

    @staticmethod
    def get_point_estimate_path(output_dir: Path, name: str) -> Path:
        return output_dir / "TOB_QMC" / "trees" / f"{name}.tree"

    @staticmethod
    def get_log_path(output_dir: Path, name: str) -> Path:
        return output_dir / "TOB_QMC" / "logs" / f"{name}.log"
