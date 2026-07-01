from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from scripts.lib.experiment import ASTRAL3Config
from scripts.lib.inference.inference import ConsensusMethod, TreeInferenceMethod
from scripts.lib.inference.runners.base import _BaseRunner

# Quartet/bipartition params are fixed for now; the suffix disambiguates folders
# when they become configurable (M4+). runASTRAL3.sh writes into this folder.
ASTRAL3_QUARTET = 11
ASTRAL3_BIPARTITIONS = 5


class ASTRAL3Runner(_BaseRunner):
    VARIANT = f"PCH_ASTRAL_3({ASTRAL3_QUARTET},{ASTRAL3_BIPARTITIONS})"

    # Strategy → (bipartition-source short name, .trees path parts under output_dir).
    _STRATEGY_SOURCE = {
        ASTRAL3Config.BipartitionStrategy.MP4_TREES: ("mp4", ("MP4", "trees")),
        ASTRAL3Config.BipartitionStrategy.GA_TREES: ("ga", ("GA", "trees1")),
    }

    # Strategy → upstream method producing its bipartitions.
    _STRATEGY_METHOD = {
        ASTRAL3Config.BipartitionStrategy.MP4_TREES: TreeInferenceMethod.MP,
        ASTRAL3Config.BipartitionStrategy.GA_TREES: TreeInferenceMethod.GA,
    }

    @staticmethod
    def dependencies(config: BaseModel) -> list[TreeInferenceMethod]:
        # Heuristic ASTRAL reads the selected strategies' tree sets; exact has none.
        assert isinstance(config, ASTRAL3Config)
        if config.is_exact:
            return []
        methods: list[TreeInferenceMethod] = []
        for s in config.effective_strategies:  # preserve order, dedup
            m = ASTRAL3Runner._STRATEGY_METHOD[s]
            if m not in methods:
                methods.append(m)
        return methods

    @staticmethod
    def build_argv(
        runid: str, input_csv: Path, name: str, output_dir: Path, config: BaseModel
    ) -> list[str]:
        # Q/B fixed. -V is the single source of truth for the output folder name.
        assert isinstance(config, ASTRAL3Config)
        argv = [
            "bash",
            "scripts/sh/runASTRAL3.sh",
            "-H",
            runid,
            "-i",
            str(input_csv),
            "-o",
            str(output_dir),
            "-V",
            ASTRAL3Runner.VARIANT,
            "-n",
            name,
        ]
        if config.is_exact:
            argv.append("-x")
        else:
            sources = ",".join(
                ASTRAL3Runner._STRATEGY_SOURCE[s][0]
                for s in config.effective_strategies
            )
            argv += ["-S", sources]
        return argv

    @staticmethod
    def point_estimate_path(output_dir: Path, name: str) -> Path:
        return output_dir / ASTRAL3Runner.VARIANT / "trees" / f"{name}.tree"

    @staticmethod
    def group_estimate_path(output_dir: Path, name: str) -> Optional[Path]:
        return None

    @staticmethod
    def consensus_method() -> Optional[ConsensusMethod]:
        return None

    @staticmethod
    def log_path(output_dir: Path, name: str) -> Path:
        return output_dir / ASTRAL3Runner.VARIANT / "logs" / f"{name}.log"
