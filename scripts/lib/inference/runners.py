from pathlib import Path
from typing import Optional

from scripts.lib.inference.inference import TreeInferenceMethod


def build_argv(
    method: TreeInferenceMethod,
    runid: str,
    input_csv: Path,
    name: str,
    output_dir: Path,
) -> list[str]:
    if method is TreeInferenceMethod.MP:
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
    raise NotImplementedError(f"No runner for {method}")


def point_estimate_path(
    method: TreeInferenceMethod, output_dir: Path, name: str
) -> Path:
    if method is TreeInferenceMethod.MP:
        return output_dir / "MP4" / "trees" / f"{name}-maj.tree"
    raise NotImplementedError(f"No runner for {method}")


def group_estimate_path(
    method: TreeInferenceMethod, output_dir: Path, name: str
) -> Optional[Path]:
    if method is TreeInferenceMethod.MP:
        return output_dir / "MP4" / "trees" / f"{name}.trees"
    raise NotImplementedError(f"No runner for {method}")


def consensus_method(method: TreeInferenceMethod) -> Optional[str]:
    if method is TreeInferenceMethod.MP:
        return "majority"
    raise NotImplementedError(f"No runner for {method}")


def log_path(method: TreeInferenceMethod, output_dir: Path, name: str) -> Path:
    if method is TreeInferenceMethod.MP:
        return output_dir / "MP4" / "logs" / f"{name}.log"
    raise NotImplementedError(f"No runner for {method}")
