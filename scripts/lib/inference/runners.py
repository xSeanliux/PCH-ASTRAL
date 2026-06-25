from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from scripts.lib.inference.inference import TreeInferenceMethod

# runASTRAL.sh -q 11 -b 5 writes into a folder literally named "ASTRAL(11,5)".
ASTRAL_VARIANT = "ASTRAL(11,5)"


def build_argv(
    method: TreeInferenceMethod,
    runid: str,
    input_csv: Path,
    name: str,
    output_dir: Path,
    config: BaseModel,
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
    if method is TreeInferenceMethod.GA:
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
    if method is TreeInferenceMethod.PCH_ASTRAL3:
        # ponytail: Q=11,B=5 fixed; heuristic mode uses MP4+GA bipartitions per
        # the script. Map config.bipartition_strategies to runASTRAL params later.
        argv = [
            "bash",
            "scripts/sh/runASTRAL.sh",
            "-H",
            runid,
            "-i",
            str(input_csv),
            "-o",
            str(output_dir),
            "-q",
            "11",
            "-b",
            "5",
            "-n",
            name,
        ]
        if getattr(config, "is_exact", False):
            argv.append("-x")
        return argv
    raise NotImplementedError(f"No runner for {method}")


def point_estimate_path(
    method: TreeInferenceMethod, output_dir: Path, name: str
) -> Path:
    if method is TreeInferenceMethod.MP:
        return output_dir / "MP4" / "trees" / f"{name}-maj.tree"
    if method is TreeInferenceMethod.GA:
        return output_dir / "GA" / "trees" / f"{name}.tree"
    if method is TreeInferenceMethod.PCH_ASTRAL3:
        return output_dir / ASTRAL_VARIANT / "trees" / f"{name}.tree"
    raise NotImplementedError(f"No runner for {method}")


def group_estimate_path(
    method: TreeInferenceMethod, output_dir: Path, name: str
) -> Optional[Path]:
    if method is TreeInferenceMethod.MP:
        return output_dir / "MP4" / "trees" / f"{name}.trees"
    if method is TreeInferenceMethod.GA:
        return output_dir / "GA" / "trees1" / f"{name}.trees"
    if method is TreeInferenceMethod.PCH_ASTRAL3:
        return None
    raise NotImplementedError(f"No runner for {method}")


def consensus_method(method: TreeInferenceMethod) -> Optional[str]:
    if method is TreeInferenceMethod.MP:
        return "majority"
    if method is TreeInferenceMethod.GA:
        return "mcc"
    if method is TreeInferenceMethod.PCH_ASTRAL3:
        return None
    raise NotImplementedError(f"No runner for {method}")


def log_path(method: TreeInferenceMethod, output_dir: Path, name: str) -> Path:
    if method is TreeInferenceMethod.MP:
        return output_dir / "MP4" / "logs" / f"{name}.log"
    if method is TreeInferenceMethod.GA:
        return output_dir / "GA" / "logs" / f"{name}.log"
    if method is TreeInferenceMethod.PCH_ASTRAL3:
        return output_dir / ASTRAL_VARIANT / "logs" / f"{name}.log"
    raise NotImplementedError(f"No runner for {method}")


def missing_prerequisites(
    method: TreeInferenceMethod, config: BaseModel, output_dir: Path, name: str
) -> list[Path]:
    """Files that must exist before `method` can run, but currently don't."""
    if method is TreeInferenceMethod.PCH_ASTRAL3 and not getattr(
        config, "is_exact", False
    ):
        # Heuristic ASTRAL reads MP4 + GA tree sets to build bipartitions.
        needed = [
            output_dir / "MP4" / "trees" / f"{name}.trees",
            output_dir / "GA" / "trees1" / f"{name}.trees",
        ]
        return [p for p in needed if not p.exists()]
    return []
