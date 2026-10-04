from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from scripts.lib.inference.runners.base import Runner
from scripts.lib.model.methods import ConsensusMethod, TreeInferenceMethod

if TYPE_CHECKING:
    from scripts.lib.experiment import MP4Config  # noqa: F401  (used in the quoted base)


@dataclass(frozen=True)
class MP4Runner(Runner["MP4Config"]):
    @property
    def method(self) -> TreeInferenceMethod:
        return TreeInferenceMethod.MP

    def build_argv(
        self, runid: str, input_csv: Path, name: str, output_dir: Path
    ) -> list[str]:
        return [
            "bash",
            "scripts/sh/runMP4.sh",
            "--runid",
            runid,
            "--input",
            str(input_csv),
            "--name",
            name,
            "--output",
            str(output_dir),
        ]

    @staticmethod
    def get_point_estimate_path(output_dir: Path, name: str) -> Path:
        return output_dir / "MP4" / "trees" / f"{name}-maj.tree"

    @staticmethod
    def get_group_estimate_path(output_dir: Path, name: str) -> Path:
        return output_dir / "MP4" / "trees" / f"{name}.trees"

    @staticmethod
    def get_consensus_method() -> ConsensusMethod:
        return ConsensusMethod.MAJORITY

    @staticmethod
    def get_log_path(output_dir: Path, name: str) -> Path:
        return output_dir / "MP4" / "logs" / f"{name}.log"
