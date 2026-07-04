import hashlib
from pathlib import Path

import yaml
from pydantic import BaseModel

from scripts.lib.experiment import (
    ASTRAL3Config,
    GAConfig,
    MethodConfig,
    MP4Config,
    WeightedASTRALConfig,
    WeightedTreeQMCConfig,
)
from scripts.lib.inference.inference import TreeInferenceMethod

# The concrete method-config types (one per TreeInferenceMethod).
MethodConfigT = (
    ASTRAL3Config | WeightedASTRALConfig | WeightedTreeQMCConfig | MP4Config | GAConfig
)

METHOD_CONFIG: dict[TreeInferenceMethod, type[MethodConfigT]] = {
    TreeInferenceMethod.PCH_ASTRAL3: ASTRAL3Config,
    TreeInferenceMethod.PCH_WASTRAL: WeightedASTRALConfig,
    TreeInferenceMethod.PCH_W_TREE_QMC: WeightedTreeQMCConfig,
    TreeInferenceMethod.MP: MP4Config,
    TreeInferenceMethod.GA: GAConfig,
}


def config_for(
    methods: MethodConfig, method: TreeInferenceMethod
) -> MethodConfigT | None:
    """The enabled config for `method`, matched by type (None if not enabled).

    Keyed off the config class (`METHOD_CONFIG`), not a field name — MethodConfig's
    fields have distinct types, so isinstance picks the right one.
    """
    want = METHOD_CONFIG[method]
    for value in vars(methods).values():
        if isinstance(value, want):
            return value
    return None


def resolve_config(
    method: TreeInferenceMethod, config_file: Path | None
) -> MethodConfigT:
    """Validate the method's config from YAML (or defaults when no file).

    `model_validate` returns the concrete config type (no cast needed). Configs
    with required fields and no `config_file` raise `pydantic.ValidationError`;
    the CLI turns that into a clean `--method-config required` error.
    """
    data = yaml.safe_load(config_file.read_text()) if config_file is not None else {}
    return METHOD_CONFIG[method].model_validate(data)


def config_hash(config: BaseModel) -> str:
    return hashlib.sha256(config.model_dump_json().encode()).hexdigest()
