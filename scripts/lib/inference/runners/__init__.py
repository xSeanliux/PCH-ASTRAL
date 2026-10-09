from pydantic import BaseModel

from scripts.lib.model.methods import (
    InferenceMethod,
    NetworkInferenceMethod,
    TreeInferenceMethod,
)
from scripts.lib.inference.runners.astral3 import ASTRAL3Runner
from scripts.lib.inference.runners.base import Runner
from scripts.lib.inference.runners.camus import CamusRunner
from scripts.lib.inference.runners.ga import GARunner
from scripts.lib.inference.runners.mp4 import MP4Runner
from scripts.lib.inference.runners.snaq import SnaqRunner
from scripts.lib.inference.runners.w_tree_qmc import WTreeQmcRunner
from scripts.lib.inference.runners.wastral import WASTRALRunner

# Insertion order is the canonical method order: the scheduler's tie-break among
# independent methods (real dependency edges still come from `get_dependencies()`).
# Also the by-method lookup, e.g. `METHOD_TO_RUNNER_CLASS[dep].get_point_estimate_path`.
METHOD_TO_RUNNER_CLASS: dict[InferenceMethod, type[Runner[BaseModel]]] = {
    TreeInferenceMethod.MP: MP4Runner,
    TreeInferenceMethod.GA: GARunner,
    TreeInferenceMethod.PCH_ASTRAL3: ASTRAL3Runner,
    TreeInferenceMethod.PCH_W_TREE_QMC: WTreeQmcRunner,
    TreeInferenceMethod.PCH_WASTRAL: WASTRALRunner,
    NetworkInferenceMethod.CAMUS: CamusRunner,
    NetworkInferenceMethod.SNAQ: SnaqRunner,
}

__all__ = [
    "Runner",
    "MP4Runner",
    "GARunner",
    "ASTRAL3Runner",
    "WTreeQmcRunner",
    "CamusRunner",
    "WASTRALRunner",
    "SnaqRunner",
    "METHOD_TO_RUNNER_CLASS",
]
