from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from scripts.lib.inference.runners.base import Runner
from scripts.lib.model.methods import InferenceMethod, TreeInferenceMethod
from scripts.lib.model.strategies import BipartitionStrategy
from scripts.lib.pch import PCH_W

if TYPE_CHECKING:
    from scripts.lib.experiment import ASTRAL3Config  # noqa: F401  (used in the quoted base)


@dataclass(frozen=True)
class ASTRAL3Runner(Runner["ASTRAL3Config"]):
    # runASTRAL3.sh generates quartets via PCH_W (scripts/py/printQuartets).
    SCHEME = PCH_W
    VARIANT = f"{SCHEME.__name__}_ASTRAL3"  # -> "PCH_W_ASTRAL3"

    # Strategy → bipartition-source short name passed to runASTRAL3.sh via -S.
    _STRATEGY_TO_SOURCE = {
        BipartitionStrategy.MP4_TREES: "mp4",
        BipartitionStrategy.GA_TREES: "ga",
    }

    # Strategy → the upstream method that produces its bipartitions.
    _STRATEGY_TO_METHOD = {
        BipartitionStrategy.MP4_TREES: TreeInferenceMethod.MP,
        BipartitionStrategy.GA_TREES: TreeInferenceMethod.GA,
    }

    @property
    def method(self) -> TreeInferenceMethod:
        return TreeInferenceMethod.PCH_ASTRAL3

    def get_dependencies(self) -> list[InferenceMethod]:
        # Heuristic ASTRAL reads the selected sources' tree sets; exact has none.
        if self.config.is_exact:
            return []
        # order-preserving dedup of each source's upstream method
        return list(
            dict.fromkeys(
                ASTRAL3Runner._STRATEGY_TO_METHOD[s]
                for s in self._get_bipartition_sources()
            )
        )

    def _get_bipartition_sources(self) -> list[BipartitionStrategy]:
        """Which tree sets feed the heuristic run's bipartitions; empty config
        defaults to MP4 + GA (today's behavior).

        :raises NotImplementedError: for `binary_character`.
        """
        S = BipartitionStrategy
        sources = self.config.bipartition_strategies or [S.MP4_TREES, S.GA_TREES]
        if S.BINARY_CHARACTER in sources:
            raise NotImplementedError("binary_character bipartitions not yet supported")
        return sources

    def build_argv(
        self, runid: str, input_csv: Path, name: str, output_dir: Path
    ) -> list[str]:
        # -V is the single source of truth for the output folder name.
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
        if self.config.is_exact:
            argv.append("-x")
        else:
            sources = ",".join(
                ASTRAL3Runner._STRATEGY_TO_SOURCE[s]
                for s in self._get_bipartition_sources()
            )
            argv += ["-S", sources]
        return argv

    @staticmethod
    def get_point_estimate_path(output_dir: Path, name: str) -> Path:
        return output_dir / ASTRAL3Runner.VARIANT / "trees" / f"{name}.tree"

    @staticmethod
    def get_log_path(output_dir: Path, name: str) -> Path:
        return output_dir / ASTRAL3Runner.VARIANT / "logs" / f"{name}.log"
