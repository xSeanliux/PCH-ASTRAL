from scripts.lib.inference.inference import TreeInferenceMethod
from scripts.lib.inference.runners.astral3 import ASTRAL3Runner
from scripts.lib.inference.runners.base import Runner
from scripts.lib.inference.runners.camus import CamusRunner
from scripts.lib.inference.runners.ga import GARunner
from scripts.lib.inference.runners.mp4 import MP4Runner
from scripts.lib.inference.runners.w_tree_qmc import WTreeQmcRunner
from scripts.lib.inference.runners.wastral import WASTRALRunner

# Method -> Runner.
RUNNERS: dict[TreeInferenceMethod, Runner] = {
    TreeInferenceMethod.MP: MP4Runner(),
    TreeInferenceMethod.GA: GARunner(),
    TreeInferenceMethod.PCH_ASTRAL3: ASTRAL3Runner(),
    TreeInferenceMethod.PCH_W_TREE_QMC: WTreeQmcRunner(),
    TreeInferenceMethod.CAMUS: CamusRunner(),
    TreeInferenceMethod.PCH_WASTRAL: WASTRALRunner(),
}

__all__ = [
    "Runner",
    "MP4Runner",
    "GARunner",
    "ASTRAL3Runner",
    "WTreeQmcRunner",
    "CamusRunner",
    "WASTRALRunner",
    "RUNNERS",
]
