from dataclasses import dataclass
from typing import Optional, TypedDict
from enum import StrEnum, auto


class TreeInferenceMethod(StrEnum):
    PCH_ASTRAL3 = "pch_astral3"
    PCH_WASTRAL = "pch_wastral"
    PCH_W_TREE_QMC = "pch_w_tree_qmc"
    MP = "mp"
    GA = "ga"
    CAMUS = "camus"  # level-1 network inference (not a tree); see spec/camus/


class RunStatus(StrEnum):
    OK = "ok"  # the inference command exited 0
    FAILED = "failed"  # non-zero exit


class ConsensusMethod(StrEnum):
    PASSTHROUGH = auto()  # R calls this "average" (-m 1) but it returns all trees as-is
    MAJORITY = auto()
    MAP = auto()
    MCC = auto()


class RegistryRow(TypedDict):
    """One inference_registry.csv row — generic, keyed by dataset_id = input path."""

    dataset_id: str
    method: str
    config_hash: str
    method_config_json: str
    runtime_seconds: float
    point_estimate_newick: str
    tree_set_path: Optional[str]
    consensus_method: Optional[str]
    status: str
    ran_at: str
    log_path: Optional[str]


@dataclass
class InferenceResult:
    """One generic inference entry, keyed by dataset_id = the input path.

    Source-agnostic: identical on a simulated CSV or a real one. Sim metadata is
    recovered by joining dataset_id → simulated_data_registry.path; FN/FP live in
    scores.csv (see `pch experiment score`).
    """

    dataset_id: str
    tree_inference_method: TreeInferenceMethod
    config_hash: str
    method_config_json: str
    point_estimate_newick: str
    runtime_seconds: float
    status: RunStatus
    ran_at: str

    tree_set_path: Optional[str] = None
    consensus_method: Optional[str] = None
    log_path: Optional[str] = None

    def to_registry_row(self) -> RegistryRow:
        return {
            "dataset_id": self.dataset_id,
            "method": self.tree_inference_method.value,
            "config_hash": self.config_hash,
            "method_config_json": self.method_config_json,
            "runtime_seconds": self.runtime_seconds,
            "point_estimate_newick": self.point_estimate_newick,
            "tree_set_path": self.tree_set_path,
            "consensus_method": self.consensus_method,
            "status": self.status.value,
            "ran_at": self.ran_at,
            "log_path": self.log_path,
        }
