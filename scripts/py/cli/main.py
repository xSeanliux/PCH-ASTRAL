import json
import shutil
from enum import Enum
from pathlib import Path

import polars as pl
import typer
import yaml
from pydantic import ValidationError
from rich import print

from scripts.lib.experiment import ExperimentConfig
from scripts.lib.inference import api
from scripts.lib.inference.executor import SlurmExecutor
from scripts.lib.inference.inference import ConsensusMethod, TreeInferenceMethod
from scripts.lib.inference.method_config import resolve_config
from scripts.lib.inference import registry
from scripts.lib.inference.scoring import score
from scripts.lib.inference.summarize import summarize
from scripts.py.cli.handle_inference import handle_inference
from scripts.py.cli.handle_score import handle_score
from scripts.py.cli.handle_simulation import handle_simulation
from scripts.py.cli.handle_status import handle_status
from scripts.py.cli.schemata import SIMULATED_DATA_REGISTRY_SCHEMA


class Executor(str, Enum):
    local = "local"
    slurm = "slurm"


app = typer.Typer()
experiment = typer.Typer()
app.add_typer(experiment, name="experiment")


def _get_experiment_config(config: Path) -> ExperimentConfig:
    with open(config) as f:
        data = yaml.safe_load(f)
    return ExperimentConfig.model_validate(data)


@app.command()
def simulation(config_path: Path):
    config = _get_experiment_config(config_path)
    handle_simulation(config)


@app.command()
def infer(
    input: Path,
    output: Path,
    method: TreeInferenceMethod = typer.Option(..., "--method"),
    method_config: Path | None = None,
    json_: bool = typer.Option(False, "--json"),
):
    """Atomic inference on one dataset; renders the InferenceResult.

    Works on any CSV, simulated or not: the entry is generic, keyed by
    dataset_id = the input path. Sim metadata/FN-FP are joins/a separate step.
    """
    try:
        config = resolve_config(method, method_config)
    except ValidationError as e:
        raise typer.BadParameter(
            f"--method-config is required for method '{method.value}': {e}"
        ) from e
    result = api.infer(input, output, method, config)
    # typer.echo (not rich print): no markup parsing / soft-wrap, so [ok]/[failed]
    # survive and --json stays a single pipeable line.
    if json_:
        typer.echo(json.dumps(result.to_registry_row()))
    else:
        typer.echo(
            f"[{result.status.value}] {result.tree_inference_method.value} "
            f"in {result.runtime_seconds:.2f}s -> {result.point_estimate_newick or '(no tree)'}"
        )


@app.command(name="score")
def score_(
    estimate: Path = typer.Option(..., "--estimate", exists=True, dir_okay=False),
    reference: Path = typer.Option(..., "--reference", exists=True, dir_okay=False),
    json_: bool = typer.Option(False, "--json"),
):
    """RF-score one estimate against a reference Newick."""
    sr = score(estimate.read_text(), reference.read_text())
    # typer.echo (not rich print): machine payload, no markup parsing / soft-wrap.
    if json_:
        typer.echo(json.dumps({"fn_rate": sr.fn_rate, "fp_rate": sr.fp_rate}))
    else:
        typer.echo(f"FN {sr.fn_rate}  FP {sr.fp_rate}")


# ConsensusMethod -> consensusTree.R `-m` mode int.
_CONSENSUS_MODES = {
    ConsensusMethod.PASSTHROUGH: 1,
    ConsensusMethod.MAJORITY: 2,
    ConsensusMethod.MAP: 3,
    ConsensusMethod.MCC: 4,
}


@app.command(name="summarize")
def summarize_(
    trees: Path = typer.Option(..., "--trees"),
    output: Path = typer.Option(..., "--output"),
    consensus: ConsensusMethod = typer.Option(..., "--consensus"),
    discard: int = typer.Option(0, "--discard"),
):
    """Consensus-summarize a tree set to a single Newick."""
    out = summarize(trees, output, mode=_CONSENSUS_MODES[consensus], discard=discard)
    typer.echo(out)


@experiment.command()
def inference(
    config_path: Path,
    executor: Executor = typer.Option(Executor.local, "--executor"),
    datasets: Path | None = typer.Option(None, "--datasets"),
    method: str | None = typer.Option(None, "--method"),
    resubmits: int = typer.Option(3, "--resubmits"),
    astral_mem_gb: int | None = typer.Option(None, "--astral-mem-gb"),
    dry_run: bool = typer.Option(False, "--dry-run/--no-dry-run"),
):
    """Run enabled methods over the sim registry. `--executor slurm` fans out one
    submitit job per (condition, method); `local` (default) runs in-process."""
    config = _get_experiment_config(config_path)
    if executor is Executor.local:
        out = handle_inference(config, datasets=datasets, method=method)
        print(f"Results in [green]{out}[/green] (join to simulated_data_registry.csv).")
        return

    # submitit's AutoExecutor silently degrades to local when sbatch is absent;
    # error instead so `--executor slurm` never surprises. (dry-run needs no sbatch.)
    if not dry_run and shutil.which("sbatch") is None:
        raise typer.BadParameter(
            "SLURM executor needs `sbatch` on PATH. Use --dry-run to preview the "
            "plan, or --executor local to run in-process."
        )

    sim_registry = (
        config.experiment_folder / "simulation_data" / "simulated_data_registry.csv"
    )
    rows = list(
        pl.read_csv(sim_registry, schema=SIMULATED_DATA_REGISTRY_SCHEMA).iter_rows(
            named=True
        )
    )
    SlurmExecutor(config).fan_out(
        rows,
        method=method,
        datasets=datasets,
        resubmits=resubmits,
        astral_mem_gb=astral_mem_gb,
        dry_run=dry_run,
    )


@experiment.command(name="score")
def score_experiment(config_path: Path):
    out = handle_score(_get_experiment_config(config_path))
    print(f"Scores in [green]{out}[/green] (join to inference_registry.csv).")


@experiment.command()
def status(config_path: Path):
    handle_status(_get_experiment_config(config_path))


@experiment.command()
def compact(config_path: Path):
    out = registry.compact(_get_experiment_config(config_path).experiment_folder)
    print(f"Compacted registry -> [green]{out}[/green].")


if __name__ == "__main__":
    app()
