from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from scripts.lib.inference.inference import ConsensusMethod
from scripts.lib.inference.runners.base import _BaseRunner


class MP4Runner(_BaseRunner):
    # Stateless — methods are static; the registry holds a singleton instance.
    @staticmethod
    def build_argv(
        runid: str, input_csv: Path, name: str, output_dir: Path, config: BaseModel
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
