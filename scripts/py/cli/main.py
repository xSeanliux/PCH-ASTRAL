import typer
from pathlib import Path
from scripts.lib.experiment import ExperimentConfig
from scripts.py.cli.handle_simulation import handle_simulation
import yaml

app = typer.Typer()


def _get_experiment_config(config: Path) -> ExperimentConfig:
    with open(config) as f:
        data = yaml.safe_load(f)
    return ExperimentConfig.model_validate(data)


@app.command()
def simulation(config_path: Path):
    config = _get_experiment_config(config_path)
    handle_simulation(config)


@app.command()
def inference(config_path: Path):
    print(f"Hello {str(config_path)}, {config_path.is_dir()=}")
    print("Hello")


if __name__ == "__main__":
    app()
