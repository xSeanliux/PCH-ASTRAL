from abc import abstractmethod
from typing import ClassVar
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from scripts.lib.types import Polymorphism
from scripts.lib.model.strategies import BipartitionStrategy, NormalisationStrategy
from scripts.lib.model.guide_tree import (
    GuideTree,
    CAMUS_GUIDE_TREES,
    PHYLONET_MPL_GUIDE_TREES,
)
from scripts.lib.inference.runners.astral3 import ASTRAL3Runner
from scripts.lib.inference.runners.base import Runner
from scripts.lib.inference.runners.camus import CamusRunner
from scripts.lib.inference.runners.ga import GARunner
from scripts.lib.inference.runners.mp4 import MP4Runner
from scripts.lib.inference.runners.phylonet_mpl import PhyloNetMPLRunner
from scripts.lib.inference.runners.snaq import SnaqRunner
from scripts.lib.inference.runners.tob_qmc import TobQmcRunner
from scripts.lib.inference.runners.w_tree_qmc import WTreeQmcRunner
from scripts.lib.inference.runners.wastral import WASTRALRunner
from pathlib import Path


class SimulationParamSetting(BaseModel):
    model_config = ConfigDict(frozen=True)
    poly: Polymorphism
    homoplasy_factor: float
    tree_height: int
    n_chars: int


class ExperimentSimulationConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    n_horizontal_edges: list[int]
    n_trees: int
    n_replicas: int
    n_taxa: int
    # Label of a taxon grafted as sister to every base tree and network, so
    # inferred trees can be rooted on it. None = no outgroup.
    outgroup_label: str | None = Field(None)
    # bases: trees will be copied, configs used to generate new configs based on simulation configs.
    base_config_dir: Path
    base_trees_file: Path  # expect one file with each line a newick string.
    base_networks_dir: Path  # expect one folder, underneath each file is a network named `netX-Y.txt`, where X is the number of reticulation edges & Y is the model tree number.
    simulation_params: list[SimulationParamSetting]


class RunnableConfig(BaseModel):
    """A method's YAML block. `get_runners` is the layer between what the YAML
    says and what runs: one runner per unit of work."""

    model_config = ConfigDict(frozen=True)

    @abstractmethod
    def get_runners(self) -> list[Runner[BaseModel]]:
        """The runs this block asks for."""


class ASTRAL3Config(RunnableConfig):
    bipartition_strategies: list[BipartitionStrategy] = Field(list())
    is_exact: bool

    def get_runners(self) -> list[Runner[BaseModel]]:
        """One run."""
        return [ASTRAL3Runner(config=self)]


class WeightedASTRALConfig(RunnableConfig):
    def get_runners(self) -> list[Runner[BaseModel]]:
        """One run."""
        return [WASTRALRunner(config=self)]


class WeightedTreeQMCConfig(RunnableConfig):
    normalisation_strategy: NormalisationStrategy = NormalisationStrategy.N2

    def get_runners(self) -> list[Runner[BaseModel]]:
        """One run."""
        return [WTreeQmcRunner(config=self)]


class MP4Config(RunnableConfig):
    def get_runners(self) -> list[Runner[BaseModel]]:
        """One run."""
        return [MP4Runner(config=self)]


class GAConfig(RunnableConfig):
    def get_runners(self) -> list[Runner[BaseModel]]:
        """One run."""
        return [GARunner(config=self)]


class TobQmcConfig(RunnableConfig):
    # ponytail: no knobs; TREE-QMC's alpha (1e-7), beta (0.95) and search limit
    # (2n^2) apply. Expose them when a sweep needs them.
    def get_runners(self) -> list[Runner[BaseModel]]:
        """One run."""
        return [TobQmcRunner(config=self)]


class GuidedNetworkConfig(RunnableConfig):
    """A network method searched from a guide (start) tree; one run per guide."""

    guide_trees: frozenset[GuideTree] = Field(min_length=1)
    runner_class: ClassVar[type[Runner[BaseModel]]]

    def get_runners(self) -> list[Runner[BaseModel]]:
        """One run per guide, in sorted order (a set has none).

        Each gets its own config hash, so the registry key and resume behaviour
        match a single-guide YAML exactly.
        """
        return [
            self.runner_class(
                config=self.model_copy(update={"guide_trees": frozenset({g})})
            )
            for g in sorted(self.guide_trees)
        ]


class CamusConfig(GuidedNetworkConfig):
    outgroup_label: str  # every guide is rooted on it
    runner_class: ClassVar[type[Runner[BaseModel]]] = CamusRunner

    @field_validator("guide_trees")
    @classmethod
    def _reject_unsupported(cls, v: frozenset[GuideTree]) -> frozenset[GuideTree]:
        """:raises ValueError: if a guide is outside `CAMUS_GUIDE_TREES`."""
        bad = sorted(v - CAMUS_GUIDE_TREES)
        if bad:
            raise ValueError(
                f"unsupported CAMUS guide tree(s): {', '.join(bad)}. "
                f"Supported: {', '.join(sorted(CAMUS_GUIDE_TREES))}. "
                "CAMUS requires a rooted binary guide tree."
            )
        return v


class SnaqConfig(GuidedNetworkConfig):
    # Any guide: snaq! resolves polytomies and unroots its start tree itself.
    runner_class: ClassVar[type[Runner[BaseModel]]] = SnaqRunner
    # Julia workers, one SNaQ run each (10 runs). Excluded from the dump, so it changes
    # neither config_hash nor the recorded config: a resource knob, not a result.
    procs: int = Field(1, ge=1, exclude=True)


class PhyloNetMPLConfig(GuidedNetworkConfig):
    runner_class: ClassVar[type[Runner[BaseModel]]] = PhyloNetMPLRunner

    @field_validator("guide_trees")
    @classmethod
    def _reject_unsupported(cls, v: frozenset[GuideTree]) -> frozenset[GuideTree]:
        """:raises ValueError: if a guide is outside `PHYLONET_MPL_GUIDE_TREES`."""
        bad = sorted(v - PHYLONET_MPL_GUIDE_TREES)
        if bad:
            raise ValueError(
                f"unsupported PhyloNet-MPL guide tree(s): {', '.join(bad)}. "
                f"Supported: {', '.join(sorted(PHYLONET_MPL_GUIDE_TREES))}. "
                "-fs fixes the tree, so it must be binary as estimated."
            )
        return v


class MethodConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    astral_3: ASTRAL3Config | None = Field(None)
    wastral: WeightedASTRALConfig | None = Field(None)
    w_tree_qmc: WeightedTreeQMCConfig | None = Field(None)
    mp4: MP4Config | None = Field(None)
    gray_atkinson: GAConfig | None = Field(None)
    tob_qmc: TobQmcConfig | None = Field(None)
    camus: CamusConfig | None = Field(None)
    snaq: SnaqConfig | None = Field(None)
    phylonet_mpl: PhyloNetMPLConfig | None = Field(None)

    def get_enabled_configs(self) -> list[RunnableConfig]:
        """The configured methods, in field-declaration order."""
        fields = [
            self.astral_3,
            self.wastral,
            self.w_tree_qmc,
            self.mp4,
            self.gray_atkinson,
            self.tob_qmc,
            self.camus,
            self.snaq,
            self.phylonet_mpl,
        ]
        return [f for f in fields if f is not None]


class ExperimentConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    experiment_folder: Path  # where all experiment artifacts will be located
    simulation: ExperimentSimulationConfig
    methods: MethodConfig

    @model_validator(mode="after")
    def _match_camus_outgroup(self) -> "ExperimentConfig":
        """:raises ValueError: if CAMUS roots on a taxon the simulation doesn't graft."""
        camus = self.methods.camus
        if camus is not None and camus.outgroup_label != self.simulation.outgroup_label:
            raise ValueError(
                f"methods.camus.outgroup_label ({camus.outgroup_label!r}) must equal "
                f"simulation.outgroup_label ({self.simulation.outgroup_label!r})."
            )
        return self

    @model_validator(mode="after")
    def _require_phylonet_mpl_outgroup(self) -> "ExperimentConfig":
        """:raises ValueError: if PhyloNet-MPL runs without an outgroup to root on."""
        if self.methods.phylonet_mpl is not None and not self.simulation.outgroup_label:
            raise ValueError(
                "methods.phylonet_mpl needs simulation.outgroup_label set."
            )
        return self
