import hashlib
from pathlib import Path

import yaml
from pydantic import BaseModel

from scripts.lib.experiment import (
    ASTRAL3Config,
    CamusConfig,
    GAConfig,
    MP4Config,
    WeightedASTRALConfig,
    WeightedTreeQMCConfig,
)
from scripts.lib.model.methods import (
    InferenceMethod,
    NetworkInferenceMethod,
    TreeInferenceMethod,
)

# The concrete method-config types (one per InferenceMethod).
MethodConfigT = (
    ASTRAL3Config
    | WeightedASTRALConfig
    | WeightedTreeQMCConfig
    | MP4Config
    | GAConfig
    | CamusConfig
)

METHOD_TO_CONFIG_CLASS: dict[InferenceMethod, type[MethodConfigT]] = {
    TreeInferenceMethod.PCH_ASTRAL3: ASTRAL3Config,
    TreeInferenceMethod.PCH_WASTRAL: WeightedASTRALConfig,
    TreeInferenceMethod.PCH_W_TREE_QMC: WeightedTreeQMCConfig,
    TreeInferenceMethod.MP: MP4Config,
    TreeInferenceMethod.GA: GAConfig,
    NetworkInferenceMethod.CAMUS: CamusConfig,
}


def resolve_config(method: InferenceMethod, config_file: Path | None) -> MethodConfigT:
    """Validate the method's config from YAML (or defaults when no file).

    `model_validate` returns the concrete config type (no cast needed). Configs
    with required fields and no `config_file` raise `pydantic.ValidationError`;
    the CLI turns that into a clean `--method-config required` error.
    """
    data = yaml.safe_load(config_file.read_text()) if config_file is not None else {}
    return METHOD_TO_CONFIG_CLASS[method].model_validate(data)


def hash_config(config: BaseModel) -> str:
    """SHA-256 of the config's JSON; the registry's `config_hash` column."""
    return hashlib.sha256(config.model_dump_json().encode()).hexdigest()
