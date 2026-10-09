import hashlib
from pathlib import Path

import yaml
from pydantic import BaseModel

from scripts.lib.experiment import (
    ASTRAL3Config,
    CamusConfig,
    GAConfig,
    MP4Config,
    RunnableConfig,
    SnaqConfig,
    WeightedASTRALConfig,
    WeightedTreeQMCConfig,
)
from scripts.lib.model.methods import (
    InferenceMethod,
    NetworkInferenceMethod,
    TreeInferenceMethod,
)

METHOD_TO_CONFIG_CLASS: dict[InferenceMethod, type[RunnableConfig]] = {
    TreeInferenceMethod.PCH_ASTRAL3: ASTRAL3Config,
    TreeInferenceMethod.PCH_WASTRAL: WeightedASTRALConfig,
    TreeInferenceMethod.PCH_W_TREE_QMC: WeightedTreeQMCConfig,
    TreeInferenceMethod.MP: MP4Config,
    TreeInferenceMethod.GA: GAConfig,
    NetworkInferenceMethod.CAMUS: CamusConfig,
    NetworkInferenceMethod.SNAQ: SnaqConfig,
}


def resolve_config(method: InferenceMethod, config_file: Path | None) -> RunnableConfig:
    """Validate the method's config from YAML (or defaults when no file).

    Configs
    with required fields and no `config_file` raise `pydantic.ValidationError`;
    the CLI turns that into a clean `--method-config required` error.
    """
    data = yaml.safe_load(config_file.read_text()) if config_file is not None else {}
    return METHOD_TO_CONFIG_CLASS[method].model_validate(data)


def hash_config(config: BaseModel) -> str:
    """SHA-256 of the config's JSON; the registry's `config_hash` column."""
    return hashlib.sha256(config.model_dump_json().encode()).hexdigest()
