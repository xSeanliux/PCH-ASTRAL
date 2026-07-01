from pathlib import Path
from typing import Optional, Protocol

from pydantic import BaseModel

from scripts.lib.experiment import ASTRAL3Config
from scripts.lib.inference.inference import ConsensusMethod, TreeInferenceMethod

# Quartet/bipartition params are fixed for now; the suffix disambiguates folders
# when they become configurable (M4+). runASTRAL3.sh writes into this folder.
ASTRAL3_QUARTET = 11
ASTRAL3_BIPARTITIONS = 5


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

    def consensus_method(self) -> Optional[ConsensusMethod]: ...

    def log_path(self, output_dir: Path, name: str) -> Path: ...

    def dependencies(self, config: BaseModel) -> list[TreeInferenceMethod]: ...

    def missing_prerequisites(
        self, config: BaseModel, output_dir: Path, name: str
    ) -> list[Path]: ...


class _BaseRunner:
    """Shared defaults. Runners are stateless; methods are static."""

    @staticmethod
    def dependencies(config: BaseModel) -> list[TreeInferenceMethod]:
        return []  # most methods stand alone

    def missing_prerequisites(
        self, config: BaseModel, output_dir: Path, name: str
    ) -> list[Path]:
        # Generic: each dependency's group_estimate_path IS the prereq .trees file.
        missing = []
        for dep in self.dependencies(config):
            p = RUNNERS[dep].group_estimate_path(output_dir, name)
            if p is None or not p.exists():
                missing.append(p)
        return missing


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


class GARunner(_BaseRunner):
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


class ASTRAL3Runner(_BaseRunner):
    VARIANT = f"PCH_ASTRAL_3({ASTRAL3_QUARTET},{ASTRAL3_BIPARTITIONS})"

    # Strategy → (bipartition-source short name, .trees path parts under output_dir).
    _STRATEGY_SOURCE = {
        ASTRAL3Config.BipartitionStrategy.MP4_TREES: ("mp4", ("MP4", "trees")),
        ASTRAL3Config.BipartitionStrategy.GA_TREES: ("ga", ("GA", "trees1")),
    }

    # Strategy → upstream method producing its bipartitions.
    _STRATEGY_METHOD = {
        ASTRAL3Config.BipartitionStrategy.MP4_TREES: TreeInferenceMethod.MP,
        ASTRAL3Config.BipartitionStrategy.GA_TREES: TreeInferenceMethod.GA,
    }

    @staticmethod
    def dependencies(config: BaseModel) -> list[TreeInferenceMethod]:
        # Heuristic ASTRAL reads the selected strategies' tree sets; exact has none.
        assert isinstance(config, ASTRAL3Config)
        if config.is_exact:
            return []
        methods: list[TreeInferenceMethod] = []
        for s in config.effective_strategies:  # preserve order, dedup
            m = ASTRAL3Runner._STRATEGY_METHOD[s]
            if m not in methods:
                methods.append(m)
        return methods

    @staticmethod
    def build_argv(
        runid: str, input_csv: Path, name: str, output_dir: Path, config: BaseModel
    ) -> list[str]:
        # Q/B fixed. -V is the single source of truth for the output folder name.
        assert isinstance(config, ASTRAL3Config)
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
            ASTRAL3Runner.VARIANT,
            "-n",
            name,
        ]
        if config.is_exact:
            argv.append("-x")
        else:
            sources = ",".join(
                ASTRAL3Runner._STRATEGY_SOURCE[s][0]
                for s in config.effective_strategies
            )
            argv += ["-S", sources]
        return argv

    @staticmethod
    def point_estimate_path(output_dir: Path, name: str) -> Path:
        return output_dir / ASTRAL3Runner.VARIANT / "trees" / f"{name}.tree"

    @staticmethod
    def group_estimate_path(output_dir: Path, name: str) -> Optional[Path]:
        return None

    @staticmethod
    def consensus_method() -> Optional[ConsensusMethod]:
        return None

    @staticmethod
    def log_path(output_dir: Path, name: str) -> Path:
        return output_dir / ASTRAL3Runner.VARIANT / "logs" / f"{name}.log"


# Method -> Runner. Later milestones add WASTRALRunner, etc.
RUNNERS: dict[TreeInferenceMethod, Runner] = {
    TreeInferenceMethod.MP: MP4Runner(),
    TreeInferenceMethod.GA: GARunner(),
    TreeInferenceMethod.PCH_ASTRAL3: ASTRAL3Runner(),
}
