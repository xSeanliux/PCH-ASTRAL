import json
from pathlib import Path

import typer
import yaml
from pydantic import ValidationError
from rich import print

from scripts.lib.experiment import ExperimentConfig
from scripts.lib.inference import api
from scripts.lib.inference.inference import TreeInferenceMethod
from scripts.lib.inference.method_config import resolve_config
from scripts.lib.inference import registry
from scripts.lib.inference.scoring import score
from scripts.lib.inference.summarize import summarize
from scripts.py.cli.handle_inference import handle_inference
from scripts.py.cli.handle_simulation import handle_simulation

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

    Works on any CSV, simulated or not: the simulation join keys are left None
    for atomic runs (they're only stamped by the experiment pipeline).
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


_CONSENSUS_MODES = {"average": 1, "majority": 2, "map": 3, "mcc": 4}


@app.command(name="summarize")
def summarize_(
    trees: Path = typer.Option(..., "--trees"),
    output: Path = typer.Option(..., "--output"),
    consensus: str = typer.Option(..., "--consensus"),
    discard: int = typer.Option(0, "--discard"),
):
    """Consensus-summarize a tree set to a single Newick."""
    mode = _CONSENSUS_MODES.get(consensus)
    if mode is None:
        raise typer.BadParameter(
            f"--consensus must be one of {sorted(_CONSENSUS_MODES)}"
        )
    out = summarize(trees, output, mode=mode, discard=discard)
    typer.echo(out)


@experiment.command()
def inference(config_path: Path):
    out = handle_inference(_get_experiment_config(config_path))
    print(f"Results in [green]{out}[/green] (join to simulated_data_registry.csv).")


@experiment.command()
def status(experiment_folder: Path):
    csv = experiment_folder / "inference_data" / "inference_registry.csv"
    if not csv.exists():
        print(f"No inference registry at [green]{csv}[/green].")
        return
    import polars as pl

    df = pl.read_csv(csv)
    print(f"Total runs: {df.height}")
    for method, count in df["method"].value_counts().iter_rows():
        print(f"  {method}: {count}")


@experiment.command()
def compact(experiment_folder: Path):
    out = registry.compact(experiment_folder)
    print(f"Compacted registry -> [green]{out}[/green].")


if __name__ == "__main__":
    app()
