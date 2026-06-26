from pathlib import Path
from typing import Optional, Protocol

from pydantic import BaseModel

from scripts.lib.inference.inference import TreeInferenceMethod

# runASTRAL.sh -q 11 -b 5 writes into a folder literally named "ASTRAL(11,5)".
ASTRAL_VARIANT = "ASTRAL(11,5)"


class Runner(Protocol):
    def build_argv(
        self,
        runid: str,
        input_csv: Path,
        name: str,
        output_dir: Path,
        config: BaseModel,
    ) -> list[str]: ...

    def point_estimate_path(self, output_dir: Path, name: str) -> Path: ...

    def group_estimate_path(self, output_dir: Path, name: str) -> Optional[Path]: ...

    def consensus_method(self) -> Optional[str]: ...

    def log_path(self, output_dir: Path, name: str) -> Path: ...

    def missing_prerequisites(
        self, config: BaseModel, output_dir: Path, name: str
    ) -> list[Path]: ...


class MP4Runner:
    def build_argv(
        self,
        runid: str,
        input_csv: Path,
        name: str,
        output_dir: Path,
        config: BaseModel,
    ) -> list[str]:
        return [
            "bash",
            "scripts/sh/runMP4.sh",
            "--runid",
            runid,
            "--input",
            str(input_csv),
            "--name",
            name,
            "--output",
            str(output_dir),
        ]

    def point_estimate_path(self, output_dir: Path, name: str) -> Path:
        return output_dir / "MP4" / "trees" / f"{name}-maj.tree"

    def group_estimate_path(self, output_dir: Path, name: str) -> Optional[Path]:
        return output_dir / "MP4" / "trees" / f"{name}.trees"

    def consensus_method(self) -> Optional[str]:
        return "majority"

    def log_path(self, output_dir: Path, name: str) -> Path:
        return output_dir / "MP4" / "logs" / f"{name}.log"

    def missing_prerequisites(
        self, config: BaseModel, output_dir: Path, name: str
    ) -> list[Path]:
        return []


class GARunner:
    def build_argv(
        self,
        runid: str,
        input_csv: Path,
        name: str,
        output_dir: Path,
        config: BaseModel,
    ) -> list[str]:
        return [
            "bash",
            "scripts/sh/runGA.sh",
            "--runid",
            runid,
            "--input",
            str(input_csv),
            "--name",
            name,
            "--output",
            str(output_dir),
        ]

    def point_estimate_path(self, output_dir: Path, name: str) -> Path:
        return output_dir / "GA" / "trees" / f"{name}.tree"

    def group_estimate_path(self, output_dir: Path, name: str) -> Optional[Path]:
        return output_dir / "GA" / "trees1" / f"{name}.trees"

    def consensus_method(self) -> Optional[str]:
        return "mcc"

    def log_path(self, output_dir: Path, name: str) -> Path:
        return output_dir / "GA" / "logs" / f"{name}.log"

    def missing_prerequisites(
        self, config: BaseModel, output_dir: Path, name: str
    ) -> list[Path]:
        return []


class ASTRAL3Runner:
    def build_argv(
        self,
        runid: str,
        input_csv: Path,
        name: str,
        output_dir: Path,
        config: BaseModel,
    ) -> list[str]:
        # ponytail: Q=11,B=5 fixed; heuristic mode uses MP4+GA bipartitions per
        # the script. Map config.bipartition_strategies to runASTRAL params later.
        argv = [
            "bash",
            "scripts/sh/runASTRAL.sh",
            "-H",
            runid,
            "-i",
            str(input_csv),
            "-o",
            str(output_dir),
            "-q",
            "11",
            "-b",
            "5",
            "-n",
            name,
        ]
        if getattr(config, "is_exact", False):
            argv.append("-x")
        return argv

    def point_estimate_path(self, output_dir: Path, name: str) -> Path:
        return output_dir / ASTRAL_VARIANT / "trees" / f"{name}.tree"

    def group_estimate_path(self, output_dir: Path, name: str) -> Optional[Path]:
        return None

    def consensus_method(self) -> Optional[str]:
        return None

    def log_path(self, output_dir: Path, name: str) -> Path:
        return output_dir / ASTRAL_VARIANT / "logs" / f"{name}.log"

    def missing_prerequisites(
        self, config: BaseModel, output_dir: Path, name: str
    ) -> list[Path]:
        """Files that must exist before the method can run, but currently don't."""
        if getattr(config, "is_exact", False):
            return []
        # Heuristic ASTRAL reads MP4 + GA tree sets to build bipartitions.
        needed = [
            output_dir / "MP4" / "trees" / f"{name}.trees",
            output_dir / "GA" / "trees1" / f"{name}.trees",
        ]
        return [p for p in needed if not p.exists()]


class WASTRALRunner:
    def build_argv(
        self,
        runid: str,
        input_csv: Path,
        name: str,
        output_dir: Path,
        config: BaseModel,
    ) -> list[str]:
        return [
            "bash",
            "scripts/sh/runWASTRAL.sh",
            "--runid",
            runid,
            "--input",
            str(input_csv),
            "--name",
            name,
            "--output",
            str(output_dir),
        ]

    def point_estimate_path(self, output_dir: Path, name: str) -> Path:
        return output_dir / "WASTRAL" / "trees" / f"{name}.tree"

    def group_estimate_path(self, output_dir: Path, name: str) -> Optional[Path]:
        return None

    def consensus_method(self) -> Optional[str]:
        return None

    def log_path(self, output_dir: Path, name: str) -> Path:
        # ponytail: runWASTRAL.sh currently writes the log under
        # trees/{name}.log; this points at logs/ per the runner contract. Reconcile
        # on the cluster (needs live verification) — either move the log or this.
        return output_dir / "WASTRAL" / "logs" / f"{name}.log"

    def missing_prerequisites(
        self, config: BaseModel, output_dir: Path, name: str
    ) -> list[Path]:
        return []


class TREEQMCRunner:
    def build_argv(
        self,
        runid: str,
        input_csv: Path,
        name: str,
        output_dir: Path,
        config: BaseModel,
    ) -> list[str]:
        # normalisation_strategy.value "n2" -> "2", "n0" -> "0". Default "2".
        strat = getattr(config, "normalisation_strategy", None)
        norm = strat.value.removeprefix("n") if strat is not None else "2"
        return [
            "bash",
            "scripts/sh/runTREEQMC.sh",
            "--runid",
            runid,
            "--input",
            str(input_csv),
            "--name",
            name,
            "--output",
            str(output_dir),
            "--norm",
            norm,
        ]

    def point_estimate_path(self, output_dir: Path, name: str) -> Path:
        return output_dir / "TREEQMC" / "trees" / f"{name}.tree"

    def group_estimate_path(self, output_dir: Path, name: str) -> Optional[Path]:
        return None

    def consensus_method(self) -> Optional[str]:
        return None

    def log_path(self, output_dir: Path, name: str) -> Path:
        # ponytail: runTREEQMC.sh currently writes the log under
        # trees/{name}.log; this points at logs/ per the runner contract. Reconcile
        # on the cluster (needs live verification) — either move the log or this.
        return output_dir / "TREEQMC" / "logs" / f"{name}.log"

    def missing_prerequisites(
        self, config: BaseModel, output_dir: Path, name: str
    ) -> list[Path]:
        return []


RUNNERS: dict[TreeInferenceMethod, Runner] = {
    TreeInferenceMethod.MP: MP4Runner(),
    TreeInferenceMethod.GA: GARunner(),
    TreeInferenceMethod.PCH_ASTRAL3: ASTRAL3Runner(),
    TreeInferenceMethod.PCH_WASTRAL: WASTRALRunner(),
    TreeInferenceMethod.PCH_W_TREE_QMC: TREEQMCRunner(),
}
