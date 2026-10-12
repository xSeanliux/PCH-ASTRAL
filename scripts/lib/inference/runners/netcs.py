import shutil
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, TextIO

import polars as pl
from Bio import Phylo

from scripts.lib.inference.runners.base import Runner
from scripts.lib.inference.runners.snaq import HYBRID
from scripts.lib.model.methods import (
    InferenceMethod,
    NetworkInferenceMethod,
    TreeInferenceMethod,
)
from scripts.lib.model.model_graph import ModelGraph
from scripts.py.cli.schemata import NETWORK_FAMILY_SCHEMA

if TYPE_CHECKING:
    from scripts.lib.experiment import NetcsConfig  # noqa: F401  (used in the quoted base)


def is_rooted_on(newick: str, leaf_label: str) -> bool:
    """Whether `leaf_label` is a leaf child of the root; a unary `(OUT)` is not."""
    root = Phylo.read(StringIO(newick), "newick").root
    return any(c.is_terminal() and c.name == leaf_label for c in root.clades)


def netcs_to_family(raw_path: Path, outgroup_label: str) -> pl.DataFrame:
    """NetCS's one network as a family; `is_best` iff rooted on the outgroup."""
    newick = raw_path.read_text().strip()
    return pl.DataFrame(
        {
            "edges_added": [len(set(HYBRID.findall(newick)))],
            "network_newick": [newick],
            "is_best": [is_rooted_on(newick, outgroup_label)],
        },
        schema=NETWORK_FAMILY_SCHEMA,
    )


@dataclass(frozen=True)
class NetcsRunner(Runner["NetcsConfig"]):
    """NetCS: PCH-W quartets and TOB-QMC's tree of blobs in, one level-1 network out."""

    # NetCS rerooted off the outgroup: no .net, the family still recorded.
    is_point_estimate_optional: ClassVar[bool] = True

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

    def execute(
        self, runid: str, input_csv: Path, name: str, output_dir: Path, log_file: TextIO
    ) -> int:
        """Run NetCS, then write the family CSV and, if rooted on the outgroup, the .net.

        :returns: the exit code; the family is written only on 0.
        """
        returncode = super().execute(runid, input_csv, name, output_dir, log_file)
        if returncode == 0:
            outgroup_label = ModelGraph.from_dataset(input_csv).outgroup_label
            assert outgroup_label is not None, "runNETCS.sh fails without an outgroup"
            net = self.get_point_estimate_path(output_dir, name)
            raw = net.with_name(f"{name}.raw.net")
            family = netcs_to_family(raw, outgroup_label)
            family.write_csv(self.get_group_estimate_path(output_dir, name))
            if family["is_best"][0]:
                shutil.copyfile(raw, net)
        return returncode

    @staticmethod
    def get_point_estimate_path(output_dir: Path, name: str) -> Path:
        """NetCS's network, written only when rooted on the outgroup."""
        return output_dir / "NETCS" / "networks" / f"{name}.net"

    @staticmethod
    def get_group_estimate_path(output_dir: Path, name: str) -> Path:
        """Family CSV: the one network."""
        return output_dir / "NETCS" / "networks" / f"{name}.family.csv"

    @staticmethod
    def get_log_path(output_dir: Path, name: str) -> Path:
        """The run log; holds NetCS's rooting verdict."""
        return output_dir / "NETCS" / "logs" / f"{name}.log"
