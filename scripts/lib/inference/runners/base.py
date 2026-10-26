import os
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Generic, Protocol, TextIO, TypeVar

from pydantic import BaseModel

from scripts.lib.model.guide_tree import GuideTree
from scripts.lib.model.strategies import QuartetGenerationStrategy
from scripts.lib.pch import STRATEGY_TO_SCHEME, print_quartets_for_astral3
from scripts.lib.types import Dataset
from scripts.lib.model.methods import (
    ConsensusMethod,
    InferenceMethod,
    TreeInferenceMethod,
)

if TYPE_CHECKING:
    from scripts.lib.experiment import GuidedNetworkConfig

# Covariant: `Runner[ASTRAL3Config]` is a `Runner[BaseModel]`; `config` is read-only.
ConfigT = TypeVar("ConfigT", bound=BaseModel, covariant=True)


@dataclass(frozen=True)
class Runner(ABC, Generic[ConfigT]):
    """One run of one method: owns its config, so it owns its command and paths.

    A run is OK iff `execute` returns 0 and the required estimate exists (see
    `api.infer`): the point estimate if declared, else the group estimate; only the
    group estimate if `is_point_estimate_optional`.
    """

    config: ConfigT  # what `hash_config` hashes
    is_point_estimate_optional: ClassVar[bool] = False

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

    def execute(
        self, runid: str, input_csv: Path, name: str, output_dir: Path, log_file: TextIO
    ) -> int:
        """Run this method, logging to `log_file`; `api.infer` calls this.

        Runs `build_argv`; override to add post-processing.

        :returns: the exit code.
        """
        return subprocess.run(
            self.build_argv(runid, input_csv, name, output_dir),
            check=False,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        ).returncode

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
        """The single estimate (a tree or a network); None if the method has none."""

    @staticmethod
    def get_group_estimate_path(output_dir: Path, name: str) -> Path | None:
        """The set the point estimate summarises (trees, a network family)."""
        return None

    @staticmethod
    def get_consensus_method() -> ConsensusMethod | None:
        """How the point estimate summarises the group; None if it doesn't."""
        return None


class QuartetBasedConfig(Protocol):
    """A config of a method that reads quartets; `get_runners` splits the set."""

    @property
    def quartet_generation(self) -> frozenset[QuartetGenerationStrategy]: ...


def get_quartet_generation(config: QuartetBasedConfig) -> QuartetGenerationStrategy:
    """The one quartet generation strategy of a split config."""
    (strategy,) = config.quartet_generation
    return strategy


def get_quartet_suffix(config: QuartetBasedConfig) -> str | None:
    """The run-name suffix for the strategy; None for PCH_W, so old runs keep their names."""
    strategy = get_quartet_generation(config)
    return None if strategy is QuartetGenerationStrategy.PCH_W else str(strategy)


def get_quartets_path(runid: str) -> Path:
    """Scratch quartet file of run `runid`; `write_quartets` writes it."""
    scratch = Path(os.environ.get("PCH_SCRATCH", Path.home() / "scratch"))
    return scratch / f"tmp_quartet_{runid}.txt"


def write_quartets(config: QuartetBasedConfig, input_csv: Path, runid: str) -> None:
    """Write `input_csv`'s quartets under the config's strategy, once per unit of
    weight, to `get_quartets_path(runid)`; the run script reads them via --quartets."""
    scheme = STRATEGY_TO_SCHEME[get_quartet_generation(config)]
    path = get_quartets_path(runid)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        print_quartets_for_astral3(scheme.get_quartets(Dataset.from_path(input_csv)), f)


GuidedConfigT = TypeVar("GuidedConfigT", bound="GuidedNetworkConfig", covariant=True)


@dataclass(frozen=True)
class GuidedNetworkRunner(Runner[GuidedConfigT]):
    """A network run from one guide tree; `config` is the single-guide config."""

    @property
    def guide(self) -> GuideTree:
        """The one guide this run uses; `get_runners` splits the set."""
        (guide,) = self.config.guide_trees
        return guide

    @property
    def suffix(self) -> str:
        """The guide's name, so runs on one dataset don't collide."""
        return str(self.guide)

    def get_dependencies(self) -> list[InferenceMethod]:
        """The method that produces the guide; none for `true_tree`."""
        guide = self.guide
        return [guide] if isinstance(guide, TreeInferenceMethod) else []
