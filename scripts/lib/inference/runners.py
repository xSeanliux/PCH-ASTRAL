from pathlib import Path
from typing import Optional, Protocol

from pydantic import BaseModel

from scripts.lib.experiment import ASTRAL3Config
from scripts.lib.inference.inference import TreeInferenceMethod

# Quartet/bipartition params are fixed for now; the suffix disambiguates folders
# when they become configurable (M4+). runASTRAL3.sh writes into this folder.
ASTRAL3_QUARTET = 11
ASTRAL3_BIPARTITIONS = 5
ASTRAL_VARIANT = f"PCH_ASTRAL_3({ASTRAL3_QUARTET},{ASTRAL3_BIPARTITIONS})"


class Runner(Protocol):
    """One method's command + artifact-path construction. One class per method."""

    def build_argv(
        self,
        runid: str,
        input_csv: Path,
        name: str,
        output_dir: Path,
        config: BaseModel,
    ) -> list[str]: ...

    def point_estimate_path(self, output_dir: Path, name: str) -> Path: ...

    def group_estimate_path(self, output_dir: Path, name: str) -> Optional[Path]: ...

    def consensus_method(self) -> Optional[str]: ...

    def log_path(self, output_dir: Path, name: str) -> Path: ...

    def missing_prerequisites(
        self, config: BaseModel, output_dir: Path, name: str
    ) -> list[Path]: ...


class MP4Runner:
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
    def consensus_method() -> Optional[str]:
        return "majority"

    @staticmethod
    def log_path(output_dir: Path, name: str) -> Path:
        return output_dir / "MP4" / "logs" / f"{name}.log"

    @staticmethod
    def missing_prerequisites(
        config: BaseModel, output_dir: Path, name: str
    ) -> list[Path]:
        return []


class GARunner:
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
    def consensus_method() -> Optional[str]:
        return "mcc"

    @staticmethod
    def log_path(output_dir: Path, name: str) -> Path:
        return output_dir / "GA" / "logs" / f"{name}.log"

    @staticmethod
    def missing_prerequisites(
        config: BaseModel, output_dir: Path, name: str
    ) -> list[Path]:
        return []


class ASTRAL3Runner:
    @staticmethod
    def build_argv(
        runid: str, input_csv: Path, name: str, output_dir: Path, config: BaseModel
    ) -> list[str]:
        # Q/B fixed; heuristic mode uses MP4+GA bipartitions per the script.
        # Map config.bipartition_strategies to runASTRAL params later.
        assert isinstance(config, ASTRAL3Config)
        # -V is the single source of truth for the output folder name.
        argv = [
            "bash",
            "scripts/sh/runASTRAL3.sh",
            "-H",
            runid,
            "-i",
            str(input_csv),
            "-o",
            str(output_dir),
            "-V",
            ASTRAL_VARIANT,
            "-n",
            name,
        ]
        if config.is_exact:
            argv.append("-x")
        return argv

    @staticmethod
    def point_estimate_path(output_dir: Path, name: str) -> Path:
        return output_dir / ASTRAL_VARIANT / "trees" / f"{name}.tree"

    @staticmethod
    def group_estimate_path(output_dir: Path, name: str) -> Optional[Path]:
        return None

    @staticmethod
    def consensus_method() -> Optional[str]:
        return None

    @staticmethod
    def log_path(output_dir: Path, name: str) -> Path:
        return output_dir / ASTRAL_VARIANT / "logs" / f"{name}.log"

    @staticmethod
    def missing_prerequisites(
        config: BaseModel, output_dir: Path, name: str
    ) -> list[Path]:
        """Heuristic ASTRAL reads MP4 + GA tree sets to build bipartitions."""
        assert isinstance(config, ASTRAL3Config)
        if config.is_exact:
            return []
        needed = [
            output_dir / "MP4" / "trees" / f"{name}.trees",
            output_dir / "GA" / "trees1" / f"{name}.trees",
        ]
        return [p for p in needed if not p.exists()]


# Method -> Runner. Later milestones add WASTRALRunner, etc.
RUNNERS: dict[TreeInferenceMethod, Runner] = {
    TreeInferenceMethod.MP: MP4Runner(),
    TreeInferenceMethod.GA: GARunner(),
    TreeInferenceMethod.PCH_ASTRAL3: ASTRAL3Runner(),
}
