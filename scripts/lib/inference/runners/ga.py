from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from scripts.lib.model.methods import (
    ConsensusMethod,
    InferenceMethod,
    TreeInferenceMethod,
)

if TYPE_CHECKING:
    from scripts.lib.experiment import GAConfig


@dataclass(frozen=True)
class GARunner:
    config: "GAConfig"
    suffix: str | None = None

    @property
    def method(self) -> TreeInferenceMethod:
        # A `@property` (not a field): fixed per class, can't be overridden at
        # construction (see `Runner.method` in `runners/base.py`).
        return TreeInferenceMethod.GA

    def dependencies(self) -> list[InferenceMethod]:
        return []

    def build_argv(
        self, runid: str, input_csv: Path, name: str, output_dir: Path
    ) -> list[str]:
        return [
            "bash",
            "scripts/sh/runGA.sh",
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
        return output_dir / "GA" / "trees" / f"{name}.tree"

    @staticmethod
    def group_estimate_path(output_dir: Path, name: str) -> Optional[Path]:
        return output_dir / "GA" / "trees1" / f"{name}.trees"

    @staticmethod
    def consensus_method() -> Optional[ConsensusMethod]:
        return ConsensusMethod.MCC

    @staticmethod
    def log_path(output_dir: Path, name: str) -> Path:
        return output_dir / "GA" / "logs" / f"{name}.log"
