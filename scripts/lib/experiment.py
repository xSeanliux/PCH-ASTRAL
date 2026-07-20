from pydantic import BaseModel, Field, ConfigDict
from scripts.lib.types import Polymorphism
from pathlib import Path
from enum import IntEnum, StrEnum


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
    # bases: trees will be copied, configs used to generate new configs based on simulation configs.
    base_config_dir: Path
    base_trees_file: Path  # expect one file with each line a newick string.
    base_networks_dir: Path  # expect one folder, underneath each file is a network named `netX-Y.txt`, where X is the number of reticulation edges & Y is the model tree number.
    simulation_params: list[SimulationParamSetting]


class ASTRAL3Config(BaseModel):
    model_config = ConfigDict(frozen=True)

    class BipartitionStrategy(StrEnum):
        BINARY_CHARACTER = "binary_character"
        MP4_TREES = "mp4_trees"
        GA_TREES = "ga_trees"

    bipartition_strategies: list[BipartitionStrategy] = Field(list())
    is_exact: bool


class WeightedASTRALConfig(BaseModel):
    model_config = ConfigDict(frozen=True)


class WeightedTreeQMCConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    class NormalisationStrategy(IntEnum):
        # Values are TREE-QMC --norm_atax args; only 0 and 2 valid for quartet input.
        N0 = 0
        N2 = 2

    normalisation_strategy: NormalisationStrategy = NormalisationStrategy.N2


class MP4Config(BaseModel):
    model_config = ConfigDict(frozen=True)


class GAConfig(BaseModel):
    model_config = ConfigDict(frozen=True)


class MethodConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    astral_3: ASTRAL3Config | None = Field(None)
    wastral: WeightedASTRALConfig | None = Field(None)
    w_tree_qmc: WeightedTreeQMCConfig | None = Field(None)
    mp4: MP4Config | None = Field(None)
    gray_atkinson: GAConfig | None = Field(None)


class ExperimentConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    experiment_folder: Path  # where all experiment artifacts will be located
    simulation: ExperimentSimulationConfig
    methods: MethodConfig
