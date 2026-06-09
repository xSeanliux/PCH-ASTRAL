from pydantic import BaseModel, Field
from scripts.lib.types import Polymorphism
from pathlib import Path
from enum import StrEnum


class SimulationParamSetting(BaseModel):
    poly: Polymorphism
    homoplasy_factor: float
    tree_height: int
    n_chars: int


class ExperimentSimulationConfig(BaseModel):
    n_horizontal_edges: list[int]
    n_trees: int
    n_replicas: int
    n_taxa: int
    # bases: trees will be copied, configs used to generate new configs based on simulation configs.
    base_config_dir: Path
    base_trees_file: Path
    base_networks_dir: Path
    simulation_params: list[SimulationParamSetting]


class ASTRAL3Config(BaseModel):
    class BipartitionStrategy(StrEnum):
        BINARY_CHARACTER = "binary_character"
        MP4_TREES = "mp4_trees"
        GA_TREES = "ga_trees"

    bipartition_strategies: list[BipartitionStrategy] = Field(list())
    is_exact: bool


class WeightedASTRALConfig(BaseModel): ...


class WeightedTreeQMCConfig(BaseModel):
    class NormalisationStrategy(StrEnum):
        N2 = "n2"

    normalisation_strategy: NormalisationStrategy


class MP4Config(BaseModel): ...


class GAConfig(BaseModel): ...


class MethodConfig(BaseModel):
    astral_3: ASTRAL3Config | None = Field(None)
    wastral: WeightedASTRALConfig | None = Field(None)
    w_tree_qmc: WeightedTreeQMCConfig | None = Field(None)
    mp4: MP4Config | None = Field(None)
    gray_atkinson: GAConfig | None = Field(None)


class ExperimentConfig(BaseModel):
    experiment_folder: Path  # where all experiment artifacts will be located
    simulation: ExperimentSimulationConfig
    methods: MethodConfig
