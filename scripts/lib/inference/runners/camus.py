from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from scripts.lib.experiment import CamusConfig
from scripts.lib.inference.inference import ConsensusMethod, TreeInferenceMethod


class CamusRunner:
    """CAMUS level-1 network inference. Output is an extended-newick network, not
    a tree; the point-estimate path holds that network. runCAMUS.sh is a stub for
    now (see spec/camus/inference.md) — this wires the method into the pipeline."""

    @staticmethod
    def dependencies(config: BaseModel) -> list[TreeInferenceMethod]:
        # Each guide tree declares its own dependency (None for `true_tree`).
        assert isinstance(config, CamusConfig)
        deps = (g.dependency for g in config.guide_trees)
        return list(dict.fromkeys(d for d in deps if d is not None))  # ordered dedup

    @staticmethod
    def build_argv(
        runid: str, input_csv: Path, name: str, output_dir: Path, config: BaseModel
    ) -> list[str]:
        assert isinstance(config, CamusConfig)
        return [
            "bash",
            "scripts/sh/runCAMUS.sh",
            "--runid",
            runid,
            "--input",
            str(input_csv),
            "--name",
            name,
            "--output",
            str(output_dir),
            "--guide-trees",
            ",".join(g.value for g in config.guide_trees),
        ]

    @staticmethod
    def point_estimate_path(output_dir: Path, name: str) -> Path:
        # CAMUS writes all networks (one row per k) to <prefix>.csv; runCAMUS.sh
        # sets -o to this stem. Not a single tree — see spec/camus/registry.md.
        return output_dir / "CAMUS" / "networks" / f"{name}.csv"

    @staticmethod
    def group_estimate_path(output_dir: Path, name: str) -> Optional[Path]:
        return None

    @staticmethod
    def consensus_method() -> Optional[ConsensusMethod]:
        return None

    @staticmethod
    def log_path(output_dir: Path, name: str) -> Path:
        return output_dir / "CAMUS" / "logs" / f"{name}.log"
