import hashlib
from pathlib import Path

import yaml
from pydantic import BaseModel

from scripts.lib.experiment import (
    ASTRAL3Config,
    GAConfig,
    MP4Config,
    WeightedASTRALConfig,
    WeightedTreeQMCConfig,
)
from scripts.lib.inference.inference import TreeInferenceMethod

METHOD_CONFIG: dict[TreeInferenceMethod, type[BaseModel]] = {
    TreeInferenceMethod.PCH_ASTRAL3: ASTRAL3Config,
    TreeInferenceMethod.PCH_WASTRAL: WeightedASTRALConfig,
    TreeInferenceMethod.PCH_W_TREE_QMC: WeightedTreeQMCConfig,
    TreeInferenceMethod.MP: MP4Config,
    TreeInferenceMethod.GA: GAConfig,
}


def resolve_config(method: TreeInferenceMethod, config_file: Path | None) -> BaseModel:
    cls = METHOD_CONFIG[method]
    if config_file is not None:
        return cls.model_validate(yaml.safe_load(config_file.read_text()))
    # cls() only works for all-default configs (MP4Config/GAConfig in M1).
    return cls()


def config_hash(config: BaseModel) -> str:
    return hashlib.sha256(config.model_dump_json().encode()).hexdigest()
