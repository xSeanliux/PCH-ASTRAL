from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

from pydantic import BaseModel

from scripts.lib.model.methods import ConsensusMethod, InferenceMethod


@runtime_checkable
class Runner(Protocol):
    """One run of one method: owns its config, so it owns its command and name."""

    method: InferenceMethod

    @property
    def suffix(self) -> str | None:
        """Distinguishes runs of one method on one dataset. A `@property` (see
        `config` below) so CamusRunner's narrower (always-`str`) suffix satisfies
        this read without an invariant attribute-type match."""
        ...

    @property
    def config(self) -> BaseModel:
        """What `config_hash` hashes. A `@property` (not a plain attribute) so each
        runner's own `config: ConcreteConfig` field — a narrower type — satisfies
        this read; a plain attribute would need an exact (invariant) type match."""
        ...

    def build_argv(
        self, runid: str, input_csv: Path, name: str, output_dir: Path
    ) -> list[str]: ...

    def dependencies(self) -> list[InferenceMethod]:
        """Methods whose output this run consumes; the scheduler orders and gates
        on their names, which is why these are methods and not runners."""
        ...

    @staticmethod
    def log_path(output_dir: Path, name: str) -> Path: ...


@runtime_checkable
class TreeRunner(Runner, Protocol):
    """A method that returns one tree, optionally with the set it summarises."""

    @staticmethod
    def point_estimate_path(output_dir: Path, name: str) -> Path: ...

    @staticmethod
    def group_estimate_path(output_dir: Path, name: str) -> Optional[Path]: ...

    @staticmethod
    def consensus_method() -> Optional[ConsensusMethod]: ...


@runtime_checkable
class NetworkRunner(Runner, Protocol):
    """A method that returns a network family: one network per k."""

    @staticmethod
    def family_path(output_dir: Path, name: str) -> Path: ...
