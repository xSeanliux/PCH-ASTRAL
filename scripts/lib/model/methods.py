from enum import StrEnum, auto


class InferenceMethod(StrEnum):
    """Base of every inference method. Memberless, so it can be subclassed."""


class TreeInferenceMethod(InferenceMethod):
    PCH_ASTRAL3 = "pch_astral3"
    PCH_WASTRAL = "pch_wastral"
    PCH_W_TREE_QMC = "pch_w_tree_qmc"
    MP = "mp"
    GA = "ga"


class NetworkInferenceMethod(InferenceMethod):
    CAMUS = "camus"


class RunStatus(StrEnum):
    OK = "ok"  # the inference command exited 0
    FAILED = "failed"  # non-zero exit


class ConsensusMethod(StrEnum):
    PASSTHROUGH = auto()  # R calls this "average" (-m 1) but it returns all trees as-is
    MAJORITY = auto()
    MAP = auto()
    MCC = auto()
