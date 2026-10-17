from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

import polars as pl

from scripts.lib.inference.runners.base import GuidedNetworkRunner
from scripts.lib.model.methods import NetworkInferenceMethod

if TYPE_CHECKING:
    from scripts.lib.experiment import CamusConfig  # noqa: F401  (used in the quoted base)

# CAMUS's header -> family columns; the newick is kept as written.
CAMUS_TO_COLUMN = {
    "Number of Branches": "edges_added",
    "Extended Newick": "network_newick",
    "Quartet Satisfied Percent": "quartet_satisfied_percent",
}


def camus_to_family(path: Path) -> pl.DataFrame:
    """The family of CAMUS's network CSV at `path`, one row per network.

    Each row is CAMUS's optimum for its k, so every row is `is_best`.
    """
    df = pl.read_csv(path, columns=list(CAMUS_TO_COLUMN.keys())).rename(CAMUS_TO_COLUMN)
    return df.select(
        "edges_added",
        "network_newick",
        is_best=pl.lit(True),
        quartet_satisfied_percent="quartet_satisfied_percent",
    )


@dataclass(frozen=True)
class CamusRunner(GuidedNetworkRunner["CamusConfig"]):
    """CAMUS level-1 network inference: one guide tree in, one network family out.

    `config` is the single-guide config.
    """

    @property
    def method(self) -> NetworkInferenceMethod:
        return NetworkInferenceMethod.CAMUS

    def build_argv(
        self, runid: str, input_csv: Path, name: str, output_dir: Path
    ) -> list[str]:
        return [
            "bash",
            "scripts/sh/runCAMUS.sh",
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
            "--outgroup",
            self.config.outgroup_label,
        ]

    def execute(
        self, runid: str, input_csv: Path, name: str, output_dir: Path, log_file: TextIO
    ) -> int:
        """Run CAMUS, then convert its raw `<name>.csv` to the family CSV.

        :returns: the exit code; the family is written only on 0.
        """
        returncode = super().execute(runid, input_csv, name, output_dir, log_file)
        if returncode == 0:
            family = self.get_group_estimate_path(output_dir, name)
            camus_to_family(family.with_name(f"{name}.csv")).write_csv(family)
        return returncode

    @staticmethod
    def get_point_estimate_path(output_dir: Path, name: str) -> None:
        # ponytail: no rule for picking a k yet; add one when analysis picks it
        return None

    @staticmethod
    def get_group_estimate_path(output_dir: Path, name: str) -> Path:
        # `execute` converts CAMUS's raw `<name>.csv` to this.
        return output_dir / "CAMUS" / "networks" / f"{name}.family.csv"

    @staticmethod
    def get_log_path(output_dir: Path, name: str) -> Path:
        return output_dir / "CAMUS" / "logs" / f"{name}.log"


@dataclass(frozen=True)
class CamusBidirectionalRunner(CamusRunner):
    """CAMUS with `-B`: each added event is two contact edges, one per direction.

    A separate method: own `CAMUS_BIDIRECTIONAL/` dir, same run names as CAMUS.
    """

    @property
    def method(self) -> NetworkInferenceMethod:
        """:returns: ``CAMUS_BIDIRECTIONAL``."""
        return NetworkInferenceMethod.CAMUS_BIDIRECTIONAL

    def build_argv(
        self, runid: str, input_csv: Path, name: str, output_dir: Path
    ) -> list[str]:
        """The uni argv plus ``--bidirectional`` (CAMUS ``-B``)."""
        return super().build_argv(runid, input_csv, name, output_dir) + [
            "--bidirectional"
        ]

    @staticmethod
    def get_group_estimate_path(output_dir: Path, name: str) -> Path:
        """:returns: the family CSV under `CAMUS_BIDIRECTIONAL/`."""
        return output_dir / "CAMUS_BIDIRECTIONAL" / "networks" / f"{name}.family.csv"

    @staticmethod
    def get_log_path(output_dir: Path, name: str) -> Path:
        """:returns: the log under `CAMUS_BIDIRECTIONAL/`."""
        return output_dir / "CAMUS_BIDIRECTIONAL" / "logs" / f"{name}.log"
