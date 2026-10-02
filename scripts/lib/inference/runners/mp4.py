from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from scripts.lib.model.methods import (
    ConsensusMethod,
    InferenceMethod,
    TreeInferenceMethod,
)

if TYPE_CHECKING:
    from scripts.lib.experiment import MP4Config


@dataclass(frozen=True)
class MP4Runner:
    config: "MP4Config"
    suffix: str | None = None

    @property
    def method(self) -> TreeInferenceMethod:
        return TreeInferenceMethod.MP

    def dependencies(self) -> list[InferenceMethod]:
        return []

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
    def point_estimate_path(output_dir: Path, name: str) -> Path:
        return output_dir / "MP4" / "trees" / f"{name}-maj.tree"

    @staticmethod
    def group_estimate_path(output_dir: Path, name: str) -> Optional[Path]:
        return output_dir / "MP4" / "trees" / f"{name}.trees"

    @staticmethod
    def consensus_method() -> Optional[ConsensusMethod]:
        return ConsensusMethod.MAJORITY

    @staticmethod
    def log_path(output_dir: Path, name: str) -> Path:
        return output_dir / "MP4" / "logs" / f"{name}.log"
