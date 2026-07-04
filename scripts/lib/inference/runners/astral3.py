from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from scripts.lib.experiment import ASTRAL3Config
from scripts.lib.inference.inference import ConsensusMethod

# Quartet/bipartition params are fixed for now; the suffix disambiguates folders
# when they become configurable (M4+). runASTRAL3.sh writes into this folder.
ASTRAL3_QUARTET = 11
ASTRAL3_BIPARTITIONS = 5


class ASTRAL3Runner:
    VARIANT = f"PCH_ASTRAL_3({ASTRAL3_QUARTET},{ASTRAL3_BIPARTITIONS})"

    # Strategy → bipartition-source short name passed to runASTRAL3.sh via -S.
    _STRATEGY_SOURCE = {
        ASTRAL3Config.BipartitionStrategy.MP4_TREES: "mp4",
        ASTRAL3Config.BipartitionStrategy.GA_TREES: "ga",
    }

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
                ASTRAL3Runner._STRATEGY_SOURCE[s] for s in config.effective_strategies
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
