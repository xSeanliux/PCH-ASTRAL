from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, TextIO, TypeVar

from scripts.lib.inference.runners.base import (
    Runner,
    get_quartet_suffix,
    get_quartets_path,
    write_quartets,
)
from scripts.lib.pch import print_quartets_for_astral3
from scripts.lib.model.methods import InferenceMethod, TreeInferenceMethod

if TYPE_CHECKING:
    from scripts.lib.experiment import (  # noqa: F401  (used in the quoted bases)
        TobQmcConfig,
        TreeOfBlobsConsumerConfig,
    )


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


ConsumerConfigT = TypeVar(
    "ConsumerConfigT", bound="TreeOfBlobsConsumerConfig", covariant=True
)


@dataclass(frozen=True)
class TreeOfBlobsConsumerRunner(Runner[ConsumerConfigT]):
    """A network run expanding the `tob_qmc` run of `config.tree_of_blobs`."""

    @property
    def tree_of_blobs_suffix(self) -> str | None:
        """Suffix of the `tob_qmc` run read; None (PCH_W) is the bare-stem run."""
        t = self.config.tree_of_blobs
        return None if t is None else str(t)

    @property
    def suffix(self) -> str | None:
        """The quartet strategy unless PCH_W, then `tob_<strategy>` unless PCH_W."""
        parts = [get_quartet_suffix(self.config)]
        if self.tree_of_blobs_suffix is not None:
            parts.append(f"tob_{self.tree_of_blobs_suffix}")
        return ".".join(p for p in parts if p) or None

    def get_dependencies(self) -> list[InferenceMethod]:
        """The tree of blobs it expands."""
        return [TreeInferenceMethod.TOB_QMC]

    def get_dependency_suffixes(self) -> dict[InferenceMethod, str | None]:
        """Only the matching `tob_qmc` run will do."""
        return {TreeInferenceMethod.TOB_QMC: self.tree_of_blobs_suffix}

    def get_tree_of_blobs_path(self, input_csv: Path, output_dir: Path) -> Path:
        """The tree of blobs this run reads."""
        stem, s = input_csv.stem, self.tree_of_blobs_suffix
        return TobQmcRunner.get_point_estimate_path(
            output_dir, f"{stem}.{s}" if s else stem
        )
