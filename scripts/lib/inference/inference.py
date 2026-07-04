from dataclasses import dataclass
from scripts.lib.types import Polymorphism
from typing import Optional, TypedDict
from enum import StrEnum, auto


class TreeInferenceMethod(StrEnum):
    PCH_ASTRAL3 = "pch_astral3"
    PCH_WASTRAL = "pch_wastral"
    PCH_W_TREE_QMC = "pch_w_tree_qmc"
    MP = "mp"
    GA = "ga"


class QuartetScheme(StrEnum):
    """PCH quartet-generation scheme — see scripts/lib/pch.py (PCH_O / PCH_W)."""

    O = "O"
    W = "W"


class RunStatus(StrEnum):
    OK = "ok"  # the inference command exited 0
    FAILED = "failed"  # non-zero exit


class ConsensusMethod(StrEnum):
    PASSTHROUGH = auto()  # R calls this "average" (-m 1) but it returns all trees as-is
    MAJORITY = auto()
    MAP = auto()
    MCC = auto()


class RegistryRow(TypedDict):
    """One inference_registry.csv row. Sim-key names match the simulation registry."""

    dataset_id: str
    poly_level: Optional[str]
    character_count: Optional[int]
    min_tree_height: Optional[int]
    homoplasy_factor: Optional[float]
    horizontal_edges: Optional[int]
    model_tree: Optional[int]
    replica: Optional[int]
    method: str
    config_hash: str
    method_config_json: str
    runtime_seconds: float
    point_estimate_newick: str
    tree_set_path: Optional[str]
    consensus_method: Optional[str]
    fn_rate: Optional[float]
    fp_rate: Optional[float]
    status: str
    ran_at: str
    log_path: Optional[str]


@dataclass
class InferenceResult:
    """One inference row. Sim keys are None for atomic (non-pipeline) runs."""

    dataset_id: str
    tree_inference_method: TreeInferenceMethod
    config_hash: str
    method_config_json: str
    point_estimate_newick: str
    runtime_seconds: float
    status: RunStatus
    ran_at: str

    # Simulation join keys — None when not from the simulation pipeline.
    poly: Optional[Polymorphism] = None
    homoplasy_factor: Optional[float] = None
    tree_height: Optional[int] = None
    n_chars: Optional[int] = None
    ret_edges: Optional[int] = None
    target_tree: Optional[int] = None
    replica: Optional[int] = None

    # Result / metrics.
    tree_set_path: Optional[str] = None
    consensus_method: Optional[str] = None
    fn_rate: Optional[float] = None
    fp_rate: Optional[float] = None
    log_path: Optional[str] = None

    def to_registry_row(self) -> RegistryRow:
        """Keys match the simulation registry sim-key names so the CSVs join."""
        return {
            "dataset_id": self.dataset_id,
            "poly_level": self.poly.value if self.poly else None,
            "character_count": self.n_chars,
            "min_tree_height": self.tree_height,
            "homoplasy_factor": self.homoplasy_factor,
            "horizontal_edges": self.ret_edges,
            "model_tree": self.target_tree,
            "replica": self.replica,
            "method": self.tree_inference_method.value,
            "config_hash": self.config_hash,
            "method_config_json": self.method_config_json,
            "runtime_seconds": self.runtime_seconds,
            "point_estimate_newick": self.point_estimate_newick,
            "tree_set_path": self.tree_set_path,
            "consensus_method": self.consensus_method,
            "fn_rate": self.fn_rate,
            "fp_rate": self.fp_rate,
            "status": self.status.value,
            "ran_at": self.ran_at,
            "log_path": self.log_path,
        }
