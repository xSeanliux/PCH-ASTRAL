from abc import abstractmethod
from typing import ClassVar
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from scripts.lib.types import Polymorphism
from scripts.lib.model.strategies import (
    BipartitionStrategy,
    NormalisationStrategy,
    QuartetGenerationStrategy,
)
from scripts.lib.model.guide_tree import (
    GuideTree,
    GUIDE_TREES,
    CAMUS_GUIDE_TREES,
    SNAQ_GUIDE_TREES,
)
from scripts.lib.inference.runners.astral3 import ASTRAL3Runner
from scripts.lib.inference.runners.base import Runner
from scripts.lib.inference.runners.brooqs import BrooqsRunner
from scripts.lib.inference.runners.camus import CamusBidirectionalRunner, CamusRunner
from scripts.lib.inference.runners.ga import GARunner
from scripts.lib.inference.runners.mp4 import MP4Runner
from scripts.lib.inference.runners.netcs import NetcsRunner
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


def quartet_generation_field() -> frozenset[QuartetGenerationStrategy]:
    """A quartet-based network config's strategies: one run each, default PCH_W."""
    return Field(frozenset({QuartetGenerationStrategy.PCH_W}), min_length=1)


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
    # QTT level: an edge with p below it is contracted into a blob. TREE-QMC's 1e-7
    # needs hundreds of gene trees per 4-taxon set; PCH-W gives ~20.
    alpha: float = Field(1e-7, gt=0, lt=1)
    # Min p-value search per edge: 3-fix-1-alter (the TOB-QMC paper's), or TREE-QMC's
    # default bipartition search, capped at 2n^2 4-taxon sets. beta stays 0.95.
    three_fix_one_alter: bool = True

    def get_runners(self) -> list[Runner[BaseModel]]:
        """One run."""
        return [TobQmcRunner(config=self)]


class BrooqsConfig(RunnableConfig):
    # BROOQS's defaults plus `--rooted`.
    quartet_generation: frozenset[QuartetGenerationStrategy] = (
        quartet_generation_field()
    )

    def get_runners(self) -> list[Runner[BaseModel]]:
        """One run per quartet generation strategy, in sorted order."""
        return [
            BrooqsRunner(
                config=self.model_copy(update={"quartet_generation": frozenset({q})})
            )
            for q in sorted(self.quartet_generation)
        ]


class NetcsConfig(RunnableConfig):
    quartet_generation: frozenset[QuartetGenerationStrategy] = (
        quartet_generation_field()
    )

    def get_runners(self) -> list[Runner[BaseModel]]:
        """One run per quartet generation strategy, in sorted order."""
        return [
            NetcsRunner(
                config=self.model_copy(update={"quartet_generation": frozenset({q})})
            )
            for q in sorted(self.quartet_generation)
        ]


class GuidedNetworkConfig(RunnableConfig):
    """A network method searched from a guide (start) tree; one run per guide."""

    guide_trees: frozenset[GuideTree] = Field(min_length=1)
    runner_class: ClassVar[type[Runner[BaseModel]]]
    supported_guides: ClassVar[frozenset[GuideTree]] = GUIDE_TREES
    guide_requirement: ClassVar[str] = ""  # why the others are rejected

    @field_validator("guide_trees")
    @classmethod
    def _reject_unsupported(cls, v: frozenset[GuideTree]) -> frozenset[GuideTree]:
        """:raises ValueError: if a guide is outside `supported_guides`."""
        bad = sorted(v - cls.supported_guides)
        if bad:
            raise ValueError(
                f"unsupported guide tree(s): {', '.join(bad)}. "
                f"Supported: {', '.join(sorted(cls.supported_guides))}. "
                f"{cls.guide_requirement}"
            )
        return v

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
    quartet_generation: frozenset[QuartetGenerationStrategy] = (
        quartet_generation_field()
    )
    runner_class: ClassVar[type[Runner[BaseModel]]] = CamusRunner
    supported_guides: ClassVar[frozenset[GuideTree]] = CAMUS_GUIDE_TREES
    guide_requirement: ClassVar[str] = "CAMUS requires a rooted binary guide tree."

    def get_runners(self) -> list[Runner[BaseModel]]:
        """One run per guide x quartet generation strategy."""
        return [
            r
            for q in sorted(self.quartet_generation)
            for r in GuidedNetworkConfig.get_runners(
                self.model_copy(update={"quartet_generation": frozenset({q})})
            )
        ]


class CamusBidirectionalConfig(CamusConfig):
    runner_class: ClassVar[type[Runner[BaseModel]]] = CamusBidirectionalRunner


class SnaqConfig(GuidedNetworkConfig):
    # Any species tree: snaq! resolves polytomies and unroots its start tree itself.
    runner_class: ClassVar[type[Runner[BaseModel]]] = SnaqRunner
    supported_guides: ClassVar[frozenset[GuideTree]] = SNAQ_GUIDE_TREES
    guide_requirement: ClassVar[str] = "A tree of blobs is not a species tree."
    # Julia workers, one SNaQ run each (10 runs). Excluded from the dump, so it changes
    # neither config_hash nor the recorded config: a resource knob, not a result.
    procs: int = Field(1, ge=1, exclude=True)
    quartet_generation: frozenset[QuartetGenerationStrategy] = (
        quartet_generation_field()
    )

    def get_runners(self) -> list[Runner[BaseModel]]:
        """One run per guide x quartet generation strategy."""
        return [
            r
            for q in sorted(self.quartet_generation)
            for r in GuidedNetworkConfig.get_runners(
                self.model_copy(update={"quartet_generation": frozenset({q})})
            )
        ]


class MethodConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    astral_3: ASTRAL3Config | None = Field(None)
    wastral: WeightedASTRALConfig | None = Field(None)
    w_tree_qmc: WeightedTreeQMCConfig | None = Field(None)
    mp4: MP4Config | None = Field(None)
    gray_atkinson: GAConfig | None = Field(None)
    tob_qmc: TobQmcConfig | None = Field(None)
    brooqs: BrooqsConfig | None = Field(None)
    netcs: NetcsConfig | None = Field(None)
    camus: CamusConfig | None = Field(None)
    camus_bidirectional: CamusBidirectionalConfig | None = Field(None)
    snaq: SnaqConfig | None = Field(None)

    def get_enabled_configs(self) -> list[RunnableConfig]:
        """The configured methods, in field-declaration order."""
        fields = [
            self.astral_3,
            self.wastral,
            self.w_tree_qmc,
            self.mp4,
            self.gray_atkinson,
            self.tob_qmc,
            self.brooqs,
            self.netcs,
            self.camus,
            self.camus_bidirectional,
            self.snaq,
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
        m = self.methods
        for field, camus in (
            ("camus", m.camus),
            ("camus_bidirectional", m.camus_bidirectional),
        ):
            if (
                camus is not None
                and camus.outgroup_label != self.simulation.outgroup_label
            ):
                raise ValueError(
                    f"methods.{field}.outgroup_label ({camus.outgroup_label!r}) must "
                    f"equal simulation.outgroup_label ({self.simulation.outgroup_label!r})."
                )
        return self
