from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel

from scripts.lib.model.methods import ConsensusMethod, InferenceMethod

# Covariant: `Runner[ASTRAL3Config]` is a `Runner[BaseModel]`; `config` is read-only.
ConfigT = TypeVar("ConfigT", bound=BaseModel, covariant=True)


@dataclass(frozen=True)
class Runner(ABC, Generic[ConfigT]):
    """One run of one method: owns its config, so it owns its command and paths.

    A run is OK iff it exits 0 and writes its point estimate, else its group
    estimate (see `api.infer`).
    """

    config: ConfigT  # what `hash_config` hashes

    @property
    @abstractmethod
    def method(self) -> InferenceMethod: ...

    @property
    def suffix(self) -> str | None:
        """Distinguishes runs of one method on one dataset."""
        return None

    def get_run_name(self, stem: str) -> str:
        """On-disk name of this run: the dataset stem, plus the suffix if any."""
        return f"{stem}.{self.suffix}" if self.suffix else stem

    @abstractmethod
    def build_argv(
        self, runid: str, input_csv: Path, name: str, output_dir: Path
    ) -> list[str]:
        """The command line that runs this method."""

    def get_dependencies(self) -> list[InferenceMethod]:
        """Methods whose output this run consumes; the scheduler orders and gates
        on their names, which is why these are methods and not runners."""
        return []

    # Path getters are static: `guide_tree.py` looks a point estimate up by method alone.
    @staticmethod
    @abstractmethod
    def get_log_path(output_dir: Path, name: str) -> Path: ...

    @staticmethod
    @abstractmethod
    def get_point_estimate_path(output_dir: Path, name: str) -> Path | None:
        """The single estimate (a tree); None if the method has none."""

    @staticmethod
    def get_group_estimate_path(output_dir: Path, name: str) -> Path | None:
        """The set the point estimate summarises (trees, a network family)."""
        return None

    @staticmethod
    def get_consensus_method() -> ConsensusMethod | None:
        """How the point estimate summarises the group; None if it doesn't."""
        return None
