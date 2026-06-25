import json
from pathlib import Path

import typer
import yaml
from rich import print

from scripts.lib.experiment import ExperimentConfig
from scripts.lib.inference import api
from scripts.lib.inference.inference import TreeInferenceMethod
from scripts.lib.inference.methods import resolve_config
from scripts.lib.inference import registry
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
    method: TreeInferenceMethod = TreeInferenceMethod.MP,
    method_config: Path | None = None,
    json_: bool = typer.Option(False, "--json"),
):
    """Atomic inference on one dataset; renders the InferenceResult."""
    result = api.infer(input, output, method, resolve_config(method, method_config))
    if json_:
        print(json.dumps(result.to_registry_row()))
    else:
        print(
            f"[{result.status}] {result.tree_inference_method.value} "
            f"in {result.runtime_seconds:.2f}s -> {result.point_estimate_newick or '(no tree)'}"
        )


@experiment.command()
def inference(config_path: Path):
    handle_inference(_get_experiment_config(config_path))


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
