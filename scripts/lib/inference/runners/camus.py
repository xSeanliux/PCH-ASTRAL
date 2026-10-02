from pathlib import Path

from pydantic import BaseModel

from scripts.lib.experiment import CamusConfig
from scripts.lib.model.methods import TreeInferenceMethod


class CamusRunner:
    """CAMUS level-1 network inference: one guide tree in, one network family out."""

    @staticmethod
    def dependencies(config: BaseModel) -> list[TreeInferenceMethod]:
        # Each guide tree declares its own dependency (None for `true_tree`).
        assert isinstance(config, CamusConfig)
        deps = (g.dependency for g in config.guides)
        return list(dict.fromkeys(d for d in deps if d is not None))  # ordered dedup

    @staticmethod
    def build_argv(
        runid: str, input_csv: Path, name: str, output_dir: Path, config: BaseModel
    ) -> list[str]:
        assert isinstance(config, CamusConfig)
        # CAMUS takes one guide tree; `variants` splits a config before it gets here.
        (guide,) = config.guide_trees
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
            "--guide-tree",
            guide.value,
        ]

    @staticmethod
    def family_path(output_dir: Path, name: str) -> Path:
        # CAMUS writes `<prefix>.csv`, one row per k; runCAMUS.sh sets -o to this stem.
        return output_dir / "CAMUS" / "networks" / f"{name}.csv"

    @staticmethod
    def log_path(output_dir: Path, name: str) -> Path:
        return output_dir / "CAMUS" / "logs" / f"{name}.log"
