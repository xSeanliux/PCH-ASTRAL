import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, TextIO

import polars as pl

from scripts.lib.inference.runners.base import Runner
from scripts.lib.model.guide_tree import GuideTree
from scripts.lib.model.methods import (
    InferenceMethod,
    NetworkInferenceMethod,
    TreeInferenceMethod,
)

if TYPE_CHECKING:
    from scripts.lib.experiment import SnaqConfig  # noqa: F401  (used in the quoted base)


# `<newick>;, with -loglik <x>`; SNaQ's bug/problem notes don't match and are skipped.
NETWORK_LINE = re.compile(r"^(.*;), with -loglik (\S+)")
# Hybrid labels `#H<n>`; each appears twice, once per parent edge.
HYBRID = re.compile(r"#H\d+")


def snaq_to_family(
    networks_path: Path, best_path: Path, choice_path: Path
) -> pl.DataFrame:
    """The family of SNaQ's networks in .networks order, the chosen row as the .net.

    `run_snaq.jl` writes `.choice` = the 0-based row consistent with the outgroup, or
    `none` (no .net; no row `is_best`). Other rows keep SNaQ's newick. SNaQ writes no
    .networks when the best is a tree; the family is then the .net alone, with null
    `neg_loglik`. SNaQ's -loglik -1 (failed optimization) is null.
    """
    choice = choice_path.read_text().strip()
    lines = networks_path.read_text().splitlines() if networks_path.exists() else []
    matches = [m for line in lines if (m := NETWORK_LINE.match(line))]
    newicks = [m[1] for m in matches] or [best_path.read_text().strip()]
    index = None if choice == "none" else int(choice)
    if index is not None:
        newicks[index] = best_path.read_text().strip()
    neg_logliks = [float(m[2]) for m in matches] or [None]
    return pl.DataFrame(
        {
            "edges_added": [len(set(HYBRID.findall(n))) for n in newicks],
            "network_newick": newicks,
            "is_best": [i == index for i in range(len(newicks))],
            "neg_loglik": [None if x == -1 else x for x in neg_logliks],
        },
        schema={
            "edges_added": pl.Int64,
            "network_newick": pl.String,
            "is_best": pl.Boolean,
            "neg_loglik": pl.Float64,
        },
    )


@dataclass(frozen=True)
class SnaqRunner(Runner["SnaqConfig"]):
    """SNaQ level-1 network inference from PCH-W quartet CFs; one network out.

    `config` is the single-guide config; the guide is SNaQ's start tree.
    """

    # No network consistent with the outgroup: no .net, the family still recorded.
    is_point_estimate_optional: ClassVar[bool] = True

    @property
    def method(self) -> NetworkInferenceMethod:
        return NetworkInferenceMethod.SNAQ

    @property
    def guide(self) -> GuideTree:
        """The one start tree this run uses; `get_runners` splits the set."""
        (guide,) = self.config.guide_trees
        return guide

    @property
    def suffix(self) -> str:
        """The guide's name, so runs on one dataset don't collide."""
        return str(self.guide)

    def get_dependencies(self) -> list[InferenceMethod]:
        """The method that produces the start tree; none for `true_tree`."""
        guide = self.guide
        return [guide] if isinstance(guide, TreeInferenceMethod) else []

    def build_argv(
        self, runid: str, input_csv: Path, name: str, output_dir: Path
    ) -> list[str]:
        return [
            "bash",
            "scripts/sh/runSNAQ.sh",
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
            "--procs",
            str(self.config.procs),
        ]

    def execute(
        self, runid: str, input_csv: Path, name: str, output_dir: Path, log_file: TextIO
    ) -> int:
        """Run SNaQ, then convert its `.networks`, `.net` and `.choice` to the family CSV.

        :returns: the exit code; the family is written only on 0.
        """
        returncode = super().execute(runid, input_csv, name, output_dir, log_file)
        if returncode == 0:
            family = self.get_group_estimate_path(output_dir, name)
            snaq_to_family(
                family.with_name(f"{name}.networks"),
                family.with_name(f"{name}.net"),
                family.with_name(f"{name}.choice"),
            ).write_csv(family)
        return returncode

    @staticmethod
    def get_point_estimate_path(output_dir: Path, name: str) -> Path:
        """The chosen network, Rich newick; `run_snaq.jl` writes it if any."""
        return output_dir / "SNAQ" / "networks" / f"{name}.net"

    @staticmethod
    def get_group_estimate_path(output_dir: Path, name: str) -> Path:
        """Family CSV: the best network, then SNaQ's alternatives, with -loglik."""
        return output_dir / "SNAQ" / "networks" / f"{name}.family.csv"

    @staticmethod
    def get_log_path(output_dir: Path, name: str) -> Path:
        return output_dir / "SNAQ" / "logs" / f"{name}.log"
