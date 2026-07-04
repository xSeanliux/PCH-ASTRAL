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

    def dependencies(self, config: BaseModel) -> list[TreeInferenceMethod]:
        """Upstream methods whose output this run consumes (the scheduler orders
        + gates on these). Empty for standalone methods."""
        ...
