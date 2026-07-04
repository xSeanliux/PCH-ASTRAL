from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from scripts.lib.experiment import ASTRAL3Config
from scripts.lib.inference.inference import ConsensusMethod, TreeInferenceMethod
from scripts.lib.pch import PCH_W


class ASTRAL3Runner:
    # runASTRAL3.sh generates quartets via PCH_W (scripts/py/printQuartets).
    SCHEME = PCH_W
    VARIANT = f"{SCHEME.__name__}_ASTRAL3"  # -> "PCH_W_ASTRAL3"

    # Strategy → bipartition-source short name passed to runASTRAL3.sh via -S.
    _STRATEGY_SOURCE = {
        ASTRAL3Config.BipartitionStrategy.MP4_TREES: "mp4",
        ASTRAL3Config.BipartitionStrategy.GA_TREES: "ga",
    }

    # Strategy → the upstream method that produces its bipartitions.
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
        for s in ASTRAL3Runner._effective_strategies(config):  # order-preserving dedup
            m = ASTRAL3Runner._STRATEGY_METHOD[s]
            if m not in methods:
                methods.append(m)
        return methods

    @staticmethod
    def _effective_strategies(
        config: ASTRAL3Config,
    ) -> list[ASTRAL3Config.BipartitionStrategy]:
        """Heuristic bipartition sources; empty defaults to MP4+GA (today's behavior)."""
        S = ASTRAL3Config.BipartitionStrategy
        strategies = config.bipartition_strategies or [S.MP4_TREES, S.GA_TREES]
        if S.BINARY_CHARACTER in strategies:
            raise NotImplementedError("binary_character bipartitions not yet supported")
        return strategies

    @staticmethod
    def build_argv(
        runid: str, input_csv: Path, name: str, output_dir: Path, config: BaseModel
    ) -> list[str]:
        # -V is the single source of truth for the output folder name.
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
                ASTRAL3Runner._STRATEGY_SOURCE[s]
                for s in ASTRAL3Runner._effective_strategies(config)
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
