from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

from Bio import Phylo

from scripts.lib.inference.runners.base import Runner
from scripts.lib.model.methods import (
    InferenceMethod,
    NetworkInferenceMethod,
    TreeInferenceMethod,
)
from scripts.lib.model.model_graph import ModelGraph

if TYPE_CHECKING:
    from scripts.lib.experiment import NetcsConfig  # noqa: F401  (used in the quoted base)


def reroot_on(newick: str, leaf_label: str) -> str | None:
    """`newick` (eNewick) rerooted on `leaf_label`, topology only.

    :returns: None if the leaf is below a hybrid: no valid root there.
    """
    tree = Phylo.read(StringIO(newick), "newick")
    if any((c.name or "").startswith("#H") for c in tree.get_path(leaf_label)[:-1]):
        return None
    # Only edges on the root-to-leaf path flip, and none is a hybrid's.
    tree.root_with_outgroup(leaf_label)
    out = StringIO()
    Phylo.write(tree, out, "newick", plain=True)
    return out.getvalue().strip()


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

    def execute(
        self, runid: str, input_csv: Path, name: str, output_dir: Path, log_file: TextIO
    ) -> int:
        """Run NetCS, then reroot its network on the outgroup if it can be.

        :returns: the exit code.
        """
        returncode = super().execute(runid, input_csv, name, output_dir, log_file)
        if returncode == 0:
            outgroup_label = ModelGraph.from_dataset(input_csv).outgroup_label
            assert outgroup_label is not None, "runNETCS.sh fails without an outgroup"
            net = self.get_point_estimate_path(output_dir, name)
            rerooted = reroot_on(net.read_text().strip(), outgroup_label)
            if rerooted is not None:
                net.write_text(rerooted + "\n")
        return returncode

    @staticmethod
    def get_point_estimate_path(output_dir: Path, name: str) -> Path:
        """The network, eNewick: rerooted on the outgroup, or as NetCS wrote it if it
        cannot be."""
        return output_dir / "NETCS" / "networks" / f"{name}.net"

    @staticmethod
    def get_log_path(output_dir: Path, name: str) -> Path:
        """The run log; holds NetCS's rooting verdict."""
        return output_dir / "NETCS" / "logs" / f"{name}.log"
