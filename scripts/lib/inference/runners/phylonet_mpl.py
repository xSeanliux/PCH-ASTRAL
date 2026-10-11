import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

import polars as pl

from scripts.lib.inference.runners.base import Runner
from scripts.lib.model.guide_tree import GuideTree
from scripts.lib.model.methods import (
    InferenceMethod,
    NetworkInferenceMethod,
    TreeInferenceMethod,
)

if TYPE_CHECKING:
    from scripts.lib.experiment import PhyloNetMPLConfig  # noqa: F401  (used in the quoted base)


# `Inferred Network #<i>:`, the newick, `Total log probability: <x>`; best first.
NETWORK = re.compile(
    r"Inferred Network #\d+:\s*\n(.*;)\s*\nTotal log probability: (\S+)"
)
# Hybrid labels `#H<n>`; each appears twice, once per parent edge.
HYBRID = re.compile(r"#H\d+")


def phylonet_mpl_to_family(result_path: Path) -> pl.DataFrame:
    """The family of PhyloNet-MPL's networks, best first, newicks as written.

    `log_probability` is PhyloNet's log pseudo-likelihood; higher is better.

    :raises ValueError: if the result holds no network.
    """
    matches = NETWORK.findall(result_path.read_text())
    if not matches:
        raise ValueError(f"no network in {result_path}")
    return pl.DataFrame(
        {
            "edges_added": [len(set(HYBRID.findall(n))) for n, _ in matches],
            "network_newick": [n for n, _ in matches],
            "is_best": [i == 0 for i in range(len(matches))],
            "log_probability": [float(x) for _, x in matches],
        },
        schema={
            "edges_added": pl.Int64,
            "network_newick": pl.String,
            "is_best": pl.Boolean,
            "log_probability": pl.Float64,
        },
    )


@dataclass(frozen=True)
class PhyloNetMPLRunner(Runner["PhyloNetMPLConfig"]):
    """PhyloNet-MPL(FT): rooted PCH-W quartets plus the fixed guide tree in,
    networks out.

    `config` is the single-guide config.
    """

    @property
    def method(self) -> NetworkInferenceMethod:
        return NetworkInferenceMethod.PHYLONET_MPL

    @property
    def guide(self) -> GuideTree:
        """The one fixed tree this run uses; `get_runners` splits the set."""
        (guide,) = self.config.guide_trees
        return guide

    @property
    def suffix(self) -> str:
        """The guide's name, so runs on one dataset don't collide."""
        return str(self.guide)

    def get_dependencies(self) -> list[InferenceMethod]:
        """The method that produces the fixed tree; none for `true_tree`."""
        guide = self.guide
        return [guide] if isinstance(guide, TreeInferenceMethod) else []

    def build_argv(
        self, runid: str, input_csv: Path, name: str, output_dir: Path
    ) -> list[str]:
        return [
            "bash",
            "scripts/sh/runPhyloNetMPL.sh",
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
        ]

    def execute(
        self, runid: str, input_csv: Path, name: str, output_dir: Path, log_file: TextIO
    ) -> int:
        """Run PhyloNet, then convert its `.result` to the family CSV and the `.net`.

        :returns: the exit code; family and `.net` are written only on 0.
        """
        returncode = super().execute(runid, input_csv, name, output_dir, log_file)
        if returncode == 0:
            family_path = self.get_group_estimate_path(output_dir, name)
            family = phylonet_mpl_to_family(family_path.with_name(f"{name}.result"))
            family.write_csv(family_path)
            # Best network = the result's first newick, as written.
            self.get_point_estimate_path(output_dir, name).write_text(
                family["network_newick"][0] + "\n"
            )
        return returncode

    @staticmethod
    def get_point_estimate_path(output_dir: Path, name: str) -> Path:
        """The best network, Rich newick as PhyloNet wrote it."""
        return output_dir / "PHYLONET_MPL" / "networks" / f"{name}.net"

    @staticmethod
    def get_group_estimate_path(output_dir: Path, name: str) -> Path:
        """Family CSV: PhyloNet's networks, best first, with log pseudo-likelihoods."""
        return output_dir / "PHYLONET_MPL" / "networks" / f"{name}.family.csv"

    @staticmethod
    def get_log_path(output_dir: Path, name: str) -> Path:
        return output_dir / "PHYLONET_MPL" / "logs" / f"{name}.log"
