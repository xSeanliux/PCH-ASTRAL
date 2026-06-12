from dataclasses import dataclass
from pathlib import Path
from scripts.lib.types import Polymorphism
from typing import Optional
from enum import StrEnum
from datetime import timedelta


class TreeInferenceMethod(StrEnum):
    PCH_ASTRAL3 = "pch_astral3"
    PCH_WASTRAL = "pch_wastral"
    PCH_W_TREE_QMC = "pch_w_tree_qmc"
    MP = "mp"
    GA = "ga"


@dataclass
class InferenceResult:
    """
    The base inference result schema for every inference row.
    """

    target_tree: int
    ret_edges: int
    replica: int

    poly: Polymorphism
    tree_height: int
    homoplasy_factor: float
    n_chars: int

    point_estimate_path: Path
    group_estimate_path: Optional[Path] = (
        None  # for when the inference method returns multiple trees
    )

    consensus_method: Optional[str] = (
        None  # for when the inference method has multiple trees
    )

    tree_inference_method: TreeInferenceMethod

    metadata: dict[str, str] = {}
    runtime: timedelta
