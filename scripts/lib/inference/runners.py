from pathlib import Path
from typing import Optional, Protocol

from scripts.lib.inference.inference import TreeInferenceMethod


class Runner(Protocol):
    """One method's command + artifact-path construction. One class per method."""

    def build_argv(
        self, runid: str, input_csv: Path, name: str, output_dir: Path
    ) -> list[str]: ...

    def point_estimate_path(self, output_dir: Path, name: str) -> Path: ...

    def group_estimate_path(self, output_dir: Path, name: str) -> Optional[Path]: ...

    def consensus_method(self) -> Optional[str]: ...

    def log_path(self, output_dir: Path, name: str) -> Path: ...


class MP4Runner:
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

    def point_estimate_path(self, output_dir: Path, name: str) -> Path:
        return output_dir / "MP4" / "trees" / f"{name}-maj.tree"

    def group_estimate_path(self, output_dir: Path, name: str) -> Optional[Path]:
        return output_dir / "MP4" / "trees" / f"{name}.trees"

    def consensus_method(self) -> Optional[str]:
        return "majority"

    def log_path(self, output_dir: Path, name: str) -> Path:
        return output_dir / "MP4" / "logs" / f"{name}.log"


# Method -> Runner. Later milestones add GARunner, ASTRAL3Runner, etc.
RUNNERS: dict[TreeInferenceMethod, Runner] = {
    TreeInferenceMethod.MP: MP4Runner(),
}
