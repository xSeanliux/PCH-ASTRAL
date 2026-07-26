from pydantic import BaseModel, Field, ConfigDict, field_validator
from scripts.lib.types import Polymorphism
from scripts.lib.inference.inference import TreeInferenceMethod
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


class CamusConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    class GuideTree(StrEnum):
        """Which tree constrains the CAMUS network search.

        Membership in `_GUIDE_TREE_DEPENDENCY` is the allow-list: a member absent
        from that map is a guide CAMUS cannot accept (see `supported`).
        """

        MP = "mp"
        GA = "ga"
        ASTRAL3 = "astral3"
        TRUE_TREE = "true_tree"

        @property
        def supported(self) -> bool:
            return self in _GUIDE_TREE_DEPENDENCY

        @property
        def dependency(self) -> TreeInferenceMethod | None:
            """The method whose output supplies this guide (None = already have it).

            Only valid for supported guides; the field validator rejects the rest
            before anything can reach this.
            """
            return _GUIDE_TREE_DEPENDENCY[self]

    guide_trees: list[GuideTree]

    @field_validator("guide_trees")
    @classmethod
    def _reject_unsupported(cls, v: list[GuideTree]) -> list[GuideTree]:
        bad = [g for g in v if not g.supported]
        if bad:
            raise ValueError(
                f"unsupported CAMUS guide tree(s): {', '.join(g.value for g in bad)}. "
                "CAMUS requires a rooted, binary constraint tree and refuses anything "
                "else; mp is a majority consensus (polytomies by construction) and ga "
                "is unrooted. Supported: "
                f"{', '.join(g.value for g in _GUIDE_TREE_DEPENDENCY)}. "
                "See spec/camus/inference.md."
            )
        return v


# Guide tree -> the method whose output supplies it (None = already have it).
# ONLY these are allowed; absent = CAMUS can't use it. See `GuideTree.supported`.
_GUIDE_TREE_DEPENDENCY: dict[CamusConfig.GuideTree, TreeInferenceMethod | None] = {
    CamusConfig.GuideTree.ASTRAL3: TreeInferenceMethod.PCH_ASTRAL3,
    CamusConfig.GuideTree.TRUE_TREE: None,
}


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
