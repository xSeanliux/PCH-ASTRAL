from pydantic import BaseModel, Field, ConfigDict, field_validator
from scripts.lib.types import Polymorphism
from scripts.lib.model.strategies import BipartitionStrategy, NormalisationStrategy
from scripts.lib.model.guide_tree import GuideTree, GUIDE_TREE_DEPENDENCY
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


class ASTRAL3Config(BaseModel):
    model_config = ConfigDict(frozen=True)
    BipartitionStrategy: ClassVar[type[BipartitionStrategy]] = (
        BipartitionStrategy  # alias; enum lives in model/
    )

    bipartition_strategies: list[BipartitionStrategy] = Field(list())
    is_exact: bool


class WeightedASTRALConfig(BaseModel):
    model_config = ConfigDict(frozen=True)


class WeightedTreeQMCConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    NormalisationStrategy: ClassVar[type[NormalisationStrategy]] = (
        NormalisationStrategy  # alias; enum lives in model/
    )

    normalisation_strategy: NormalisationStrategy = NormalisationStrategy.N2


class MP4Config(BaseModel):
    model_config = ConfigDict(frozen=True)


class GAConfig(BaseModel):
    model_config = ConfigDict(frozen=True)


class CamusConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
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

    def variants(self) -> "list[tuple[CamusConfig, str]]":
        """(config, name suffix) per guide tree: CAMUS takes one guide per run, so
        each gets its own output path, config_hash, and dependency gate."""
        return [(CamusConfig(guide_trees=frozenset({g})), g.value) for g in self.guides]


class MethodConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    astral_3: ASTRAL3Config | None = Field(None)
    wastral: WeightedASTRALConfig | None = Field(None)
    w_tree_qmc: WeightedTreeQMCConfig | None = Field(None)
    mp4: MP4Config | None = Field(None)
    gray_atkinson: GAConfig | None = Field(None)
    camus: CamusConfig | None = Field(None)


class ExperimentConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    experiment_folder: Path  # where all experiment artifacts will be located
    simulation: ExperimentSimulationConfig
    methods: MethodConfig
