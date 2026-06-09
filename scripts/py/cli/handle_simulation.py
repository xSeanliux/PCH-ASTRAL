from scripts.lib.experiment import ExperimentConfig
from scripts.lib.simulation.types import SimulationConfigFactory
from scripts.py.cli.schemata import CONFIG_REGISTRY_SCHEMA, NETWORK_REGISTRY_SCHEMA
from rich import print
import os
import glob
import shutil
from rich.progress import track
from pathlib import Path
import polars as pl


def _format_path(s: str) -> str:
    return f"[green]{s}[/green]"


def handle_simulation(config: ExperimentConfig):

    simulation_config = config.simulation
    e_folder = config.experiment_folder / "simulation_data"
    print(f"Creating output folder at {_format_path(e_folder)}")
    e_folder.mkdir(parents=True, exist_ok=True)

    # copy trees over
    if 0 in simulation_config.n_horizontal_edges:
        model_tree_path = e_folder / "model_trees.txt"
        with open(simulation_config.base_trees_file) as model_tree_f:
            lines: list[str] = model_tree_f.readlines()
            assert len(lines) >= simulation_config.n_trees, (
                f"Wanted {simulation_config.n_trees} but only found {len(lines)} trees."
            )
            lines_trunc = lines[: simulation_config.n_trees]
        with open(model_tree_path, "w") as out_model_trees:
            out_model_trees.writelines(lines_trunc)
        print(
            f"Copied {simulation_config.n_trees} trees over to {_format_path(model_tree_path)}."
        )

    # copy networks over

    network_registry = [
        {
            "horizontal_edges": hor_edges,
            "model_tree": model_tree,
            "path": str(
                simulation_config.base_networks_dir / f"net{hor_edges}-{model_tree}.txt"
            ),
        }
        for hor_edges in simulation_config.n_horizontal_edges
        for model_tree in range(1, simulation_config.n_trees + 1)
        if hor_edges != 0
    ]
    output_network_folder = e_folder / "model_networks"
    output_network_folder.mkdir(parents=True, exist_ok=True)
    assert all(Path(p["path"]).is_file() for p in network_registry)
    for obj in track(network_registry, description="Copying model networks..."):
        shutil.copy(src=obj["path"], dst=output_network_folder)
    network_registry_pl = pl.DataFrame(
        data=network_registry,
        schema=NETWORK_REGISTRY_SCHEMA,
    )
    network_registry_pl.write_csv(e_folder / "network_registry.csv")
    print(
        f"Copied {len(network_registry)} networks over to {_format_path(output_network_folder)}."
    )

    # configs
    config_folder = e_folder / "configs"
    config_registry = []
    config_folder.mkdir(parents=True, exist_ok=True)
    has_tree = 0 in simulation_config.n_horizontal_edges
    has_network = len(set(simulation_config.n_horizontal_edges) - set([0])) > 0
    sim_config_factory = SimulationConfigFactory(
        base_config_path=simulation_config.base_config_dir
    )
    for params in track(
        simulation_config.simulation_params,
        description="Generating configuration files...",
    ):
        config_key = {
            "poly_level": params.poly,
            "character_count": params.n_chars,
            "min_tree_height": params.tree_height,
            "homoplasy_factor": params.homoplasy_factor,
        }
        sim_config_factory.update_params(
            **config_key,
        )

        if has_tree:
            sim_config_factory.update_params(do_borrowing=False)
            o_path = sim_config_factory.to_csv(config_folder)
            config_registry.append(
                {
                    **config_key,
                    "do_borrowing": False,
                    "path": str(o_path),
                }
            )
        if has_network:
            sim_config_factory.update_params(do_borrowing=True)
            o_path = sim_config_factory.to_csv(config_folder)
            config_registry.append(
                {
                    **config_key,
                    "do_borrowing": True,
                    "path": str(o_path),
                }
            )
    config_registry_pl = pl.DataFrame(
        data=config_registry, schema=CONFIG_REGISTRY_SCHEMA
    )
    config_registry_pl.write_csv(e_folder / "config_registry.csv")

    # simulated data
    sim_data_dir = e_folder / "simulated_data"
    sim_data_dir.mkdir(parents=True, exist_ok=True)
    for params in track(
        simulation_config.simulation_params, description="Simulating datasets..."
    ):
        pass
