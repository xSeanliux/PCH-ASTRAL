from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

import polars as pl

from scripts.lib.inference.runners.base import Runner
from scripts.lib.inference.runners.snaq import HYBRID
from scripts.lib.model.methods import (
    InferenceMethod,
    NetworkInferenceMethod,
    TreeInferenceMethod,
)
from scripts.py.cli.schemata import NETWORK_FAMILY_SCHEMA

if TYPE_CHECKING:
    from scripts.lib.experiment import BrooqsConfig  # noqa: F401  (used in the quoted base)


def brooqs_to_family(net_path: Path) -> pl.DataFrame:
    """The one-row family of BROOQS's network; a tree (no blob expanded) has 0 edges."""
    newick = net_path.read_text().strip()
    return pl.DataFrame(
        {
            "edges_added": [len(set(HYBRID.findall(newick)))],
            "network_newick": [newick],
            "is_best": [True],
        },
        schema=NETWORK_FAMILY_SCHEMA,
    )


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

    def execute(
        self, runid: str, input_csv: Path, name: str, output_dir: Path, log_file: TextIO
    ) -> int:
        """Run BROOQS, then convert its `.net` to the family CSV.

        :returns: the exit code; the family is written only on 0.
        """
        returncode = super().execute(runid, input_csv, name, output_dir, log_file)
        if returncode == 0:
            brooqs_to_family(self.get_point_estimate_path(output_dir, name)).write_csv(
                self.get_group_estimate_path(output_dir, name)
            )
        return returncode

    @staticmethod
    def get_point_estimate_path(output_dir: Path, name: str) -> Path:
        """The network, eNewick, topology only."""
        return output_dir / "BROOQS" / "networks" / f"{name}.net"

    @staticmethod
    def get_group_estimate_path(output_dir: Path, name: str) -> Path:
        """Family CSV: the network alone."""
        return output_dir / "BROOQS" / "networks" / f"{name}.family.csv"

    @staticmethod
    def get_log_path(output_dir: Path, name: str) -> Path:
        return output_dir / "BROOQS" / "logs" / f"{name}.log"
