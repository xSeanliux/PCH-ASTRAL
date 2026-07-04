from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from scripts.lib.inference.inference import ConsensusMethod, TreeInferenceMethod


class GARunner:
    @staticmethod
    def dependencies(config: BaseModel) -> list[TreeInferenceMethod]:
        return []

    @staticmethod
    def build_argv(
        runid: str, input_csv: Path, name: str, output_dir: Path, config: BaseModel
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
