from scripts.lib.inference.inference import TreeInferenceMethod
from scripts.lib.inference.runners.astral3 import (
    ASTRAL3_BIPARTITIONS,
    ASTRAL3_QUARTET,
    ASTRAL3Runner,
)
from scripts.lib.inference.runners.base import Runner
from scripts.lib.inference.runners.ga import GARunner
from scripts.lib.inference.runners.mp4 import MP4Runner

# Method -> Runner. Later milestones add WASTRALRunner, etc.
RUNNERS: dict[TreeInferenceMethod, Runner] = {
    TreeInferenceMethod.MP: MP4Runner(),
    TreeInferenceMethod.GA: GARunner(),
    TreeInferenceMethod.PCH_ASTRAL3: ASTRAL3Runner(),
}

__all__ = [
    "Runner",
    "MP4Runner",
    "GARunner",
    "ASTRAL3Runner",
    "ASTRAL3_QUARTET",
    "ASTRAL3_BIPARTITIONS",
    "RUNNERS",
]
