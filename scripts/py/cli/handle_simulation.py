from scripts.lib.experiment import ExperimentConfig
from scripts.lib.simulation.types import SimulationConfigFactory
from rich import print
import os
import glob
import shutil
from rich.progress import track
from pathlib import Path


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
    expected_network_paths: list[Path] = [
        simulation_config.base_networks_dir / f"net{hor_edges}-{replica}.txt"
        for hor_edges in simulation_config.n_horizontal_edges
        for replica in range(1, simulation_config.n_trees + 1)
        if hor_edges != 0
    ]
    output_network_folder = e_folder / "model_networks"
    output_network_folder.mkdir(parents=True, exist_ok=True)
    assert all(p.is_file() for p in expected_network_paths)
    for path in track(expected_network_paths, description="Copying model networks..."):
        shutil.copy(src=path, dst=output_network_folder)
    print(
        f"Copied {len(expected_network_paths)} networks over to {_format_path(output_network_folder)}."
    )

    # configs
    config_folder = e_folder / "configs"
    config_folder.mkdir(parents=True, exist_ok=True)
    has_tree = 0 in simulation_config.n_horizontal_edges
    has_network = len(set(simulation_config.n_horizontal_edges) - set([0])) > 0
    sim_config_factory = SimulationConfigFactory(
        base_config_path=simulation_config.base_config_dir
    )
    for params in track(
        simulation_config.simulation_params,
        description="Generating configuration files",
    ):
        sim_config_factory.update_params(
            poly_level=params.poly,
            character_count=params.n_chars,
            min_tree_height=params.tree_height,
            homoplasy_factor=params.homoplasy_factor,
        )
        if has_tree:
            sim_config_factory.update_params(do_borrowing=False)
            sim_config_factory.to_csv(config_folder)
        if has_network:
            sim_config_factory.update_params(do_borrowing=True)
            sim_config_factory.to_csv(config_folder)
