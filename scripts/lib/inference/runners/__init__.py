from scripts.lib.inference.inference import (
    InferenceMethod,
    NetworkInferenceMethod,
    TreeInferenceMethod,
)
from scripts.lib.inference.runners.astral3 import ASTRAL3Runner
from scripts.lib.inference.runners.base import NetworkRunner, Runner, TreeRunner
from scripts.lib.inference.runners.camus import CamusRunner
from scripts.lib.inference.runners.ga import GARunner
from scripts.lib.inference.runners.mp4 import MP4Runner
from scripts.lib.inference.runners.w_tree_qmc import WTreeQmcRunner
from scripts.lib.inference.runners.wastral import WASTRALRunner

TREE_RUNNERS: dict[TreeInferenceMethod, TreeRunner] = {
    TreeInferenceMethod.MP: MP4Runner(),
    TreeInferenceMethod.GA: GARunner(),
    TreeInferenceMethod.PCH_ASTRAL3: ASTRAL3Runner(),
    TreeInferenceMethod.PCH_W_TREE_QMC: WTreeQmcRunner(),
    TreeInferenceMethod.PCH_WASTRAL: WASTRALRunner(),
}

NETWORK_RUNNERS: dict[NetworkInferenceMethod, NetworkRunner] = {
    NetworkInferenceMethod.CAMUS: CamusRunner(),
}

# Method -> Runner, for what every method shares: argv, log, dependencies.
RUNNERS: dict[InferenceMethod, Runner] = {**TREE_RUNNERS, **NETWORK_RUNNERS}

__all__ = [
    "Runner",
    "TreeRunner",
    "NetworkRunner",
    "MP4Runner",
    "GARunner",
    "ASTRAL3Runner",
    "WTreeQmcRunner",
    "CamusRunner",
    "WASTRALRunner",
    "TREE_RUNNERS",
    "NETWORK_RUNNERS",
    "RUNNERS",
]
