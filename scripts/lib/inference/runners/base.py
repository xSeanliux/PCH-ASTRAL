from pathlib import Path
from typing import Optional, Protocol

from pydantic import BaseModel

from scripts.lib.inference.inference import ConsensusMethod, TreeInferenceMethod


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
        # Function-local import: RUNNERS lives in the package __init__, which imports
        # this module — importing it at top would cycle.
        from scripts.lib.inference.runners import RUNNERS

        # Generic: each dependency's group_estimate_path IS the prereq .trees file.
        missing = []
        for dep in self.dependencies(config):
            p = RUNNERS[dep].group_estimate_path(output_dir, name)
            if p is None or not p.exists():
                missing.append(p)
        return missing
