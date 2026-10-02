from pydantic import BaseModel, Field, ConfigDict, field_validator
from scripts.lib.types import Polymorphism
from scripts.lib.model.strategies import BipartitionStrategy, NormalisationStrategy
from scripts.lib.model.guide_tree import GuideTree, GUIDE_TREE_DEPENDENCY
from scripts.lib.inference.runners.astral3 import ASTRAL3Runner
from scripts.lib.inference.runners.base import Runner
from scripts.lib.inference.runners.camus import CamusRunner
from scripts.lib.inference.runners.ga import GARunner
from scripts.lib.inference.runners.mp4 import MP4Runner
from scripts.lib.inference.runners.w_tree_qmc import WTreeQmcRunner
from scripts.lib.inference.runners.wastral import WASTRALRunner
from pathlib import Path
from typing import ClassVar


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

    def get_runners(self) -> list[Runner]:
        raise NotImplementedError


class ASTRAL3Config(RunnableConfig):
    BipartitionStrategy: ClassVar[type[BipartitionStrategy]] = (
        BipartitionStrategy  # alias; enum lives in model/
    )

    bipartition_strategies: list[BipartitionStrategy] = Field(list())
    is_exact: bool

    def get_runners(self) -> list[Runner]:
        return [ASTRAL3Runner(config=self)]


class WeightedASTRALConfig(RunnableConfig):
    def get_runners(self) -> list[Runner]:
        return [WASTRALRunner(config=self)]


class WeightedTreeQMCConfig(RunnableConfig):
    NormalisationStrategy: ClassVar[type[NormalisationStrategy]] = (
        NormalisationStrategy  # alias; enum lives in model/
    )

    normalisation_strategy: NormalisationStrategy = NormalisationStrategy.N2

    def get_runners(self) -> list[Runner]:
        return [WTreeQmcRunner(config=self)]


class MP4Config(RunnableConfig):
    def get_runners(self) -> list[Runner]:
        return [MP4Runner(config=self)]


class GAConfig(RunnableConfig):
    def get_runners(self) -> list[Runner]:
        return [GARunner(config=self)]


class CamusConfig(RunnableConfig):
    GuideTree: ClassVar[type[GuideTree]] = GuideTree  # alias; the enum lives in model/

    guide_trees: frozenset[GuideTree] = Field(min_length=1)

    @field_validator("guide_trees")
    @classmethod
    def _reject_unsupported(cls, v: frozenset[GuideTree]) -> frozenset[GuideTree]:
        bad = sorted(g for g in v if not g.is_supported)
        if bad:
            raise ValueError(
                f"unsupported CAMUS guide tree(s): {', '.join(g.value for g in bad)}. "
                f"Supported: {', '.join(g.value for g in GUIDE_TREE_DEPENDENCY)}. "
                "CAMUS requires a rooted binary guide tree."
            )
        return v

    @property
    def guides(self) -> list[GuideTree]:
        """The guide trees in a fixed order; a set has none of its own."""
        return sorted(self.guide_trees)

    def get_runners(self) -> list[Runner]:
        # CAMUS takes one guide per run; each gets its own config_hash, so the
        # registry key and resume behaviour match a single-guide YAML exactly.
        return [
            CamusRunner(guide=g, config=CamusConfig(guide_trees=frozenset({g})))
            for g in self.guides
        ]


class MethodConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    astral_3: ASTRAL3Config | None = Field(None)
    wastral: WeightedASTRALConfig | None = Field(None)
    w_tree_qmc: WeightedTreeQMCConfig | None = Field(None)
    mp4: MP4Config | None = Field(None)
    gray_atkinson: GAConfig | None = Field(None)
    camus: CamusConfig | None = Field(None)

    def enabled(self) -> list[RunnableConfig]:
        """The configured methods, in field-declaration order."""
        return [v for v in vars(self).values() if v is not None]


class ExperimentConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    experiment_folder: Path  # where all experiment artifacts will be located
    simulation: ExperimentSimulationConfig
    methods: MethodConfig
