from scripts.lib.experiment import ExperimentConfig, SimulationParamSetting
from scripts.lib.simulation.types import SimulationConfigFactory
from scripts.py.cli.schemata import (
    CONFIG_REGISTRY_SCHEMA,
    MODEL_GRAPH_REGISTRY,
    SIMULATED_DATA_REGISTRY_SCHEMA,
)
from itertools import product
from rich import print
import shutil
from rich.progress import track
from pathlib import Path
import polars as pl
from hashlib import sha256
from typing import Any
import subprocess


def _format_path(s: str | Path) -> str:
    return f"[green]{str(s)}[/green]"


def stable_hash_dict(d: dict[str, Any]) -> int:
    # Encode the string to bytes, then hash it
    kv = sorted([str(k) + ":" + str(v) for k, v in d.items()])
    input_string = ";".join(kv)
    encoded_data = input_string.encode("utf-8")
    hex = sha256(encoded_data).hexdigest()
    return int(hex, 16) % (1 << 32 - 1)


def handle_simulation(config: ExperimentConfig):

    simulation_config = config.simulation
    e_folder = config.experiment_folder / "simulation_data"
    print(f"Creating output folder at {_format_path(str(e_folder))}")
    e_folder.mkdir(parents=True, exist_ok=True)

    # copy trees over
    tree_registry = []
    if 0 in simulation_config.n_horizontal_edges:
        with open(simulation_config.base_trees_file) as model_tree_f:
            lines: list[str] = model_tree_f.readlines()
            assert len(lines) >= simulation_config.n_trees, (
                f"Wanted {simulation_config.n_trees} but only found {len(lines)} trees."
            )
            lines_trunc = lines[: simulation_config.n_trees]
        for i, line in enumerate(lines_trunc, 1):
            model_tree_path = e_folder / f"model_tree_{i}.txt"
            with open(model_tree_path, "w") as out_model_tree:
                out_model_tree.write(line)
            tree_registry.append(
                {"horizontal_edges": 0, "model_tree": i, "path": str(model_tree_path)}
            )
        print(
            f"Copied {simulation_config.n_trees} trees over to {_format_path(str(model_tree_path))}."
        )

    # copy networks over

    network_registry: list[dict[str, str]] = [  # type: ignore
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
    model_graph_registry = network_registry + tree_registry
    model_graph_registry_pl = pl.DataFrame(
        data=model_graph_registry,
        schema=MODEL_GRAPH_REGISTRY,
    )
    model_graph_registry_pl.write_csv(e_folder / "model_graph_registry.csv")
    print(
        f"Copied {len(network_registry)} networks over to {_format_path(output_network_folder)}."
    )
    horedge_treenum_to_path: dict[tuple[int, int], Path] = {
        (x["horizontal_edges"], x["model_tree"]): x["path"]
        for x in model_graph_registry
    }

    # configs
    config_folder = e_folder / "configs"
    config_registry = []
    param_and_borrowing_to_config: dict[tuple["SimulationParamSetting", bool], Path] = (
        dict()
    )
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
            poly_level=params.poly,
            character_count=params.n_chars,
            min_tree_height=params.tree_height,
            homoplasy_factor=params.homoplasy_factor,
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
            param_and_borrowing_to_config[(params, False)] = o_path
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
            param_and_borrowing_to_config[(params, True)] = o_path
    config_registry_pl = pl.DataFrame(
        data=config_registry, schema=CONFIG_REGISTRY_SCHEMA
    )
    config_registry_pl.write_csv(e_folder / "config_registry.csv")

    # simulated data
    sim_data_dir = e_folder / "simulated_data"
    sim_data_dir.mkdir(parents=True, exist_ok=True)
    sim_data_registry = []
    expected_simulated_datasets = list(
        product(
            simulation_config.simulation_params,
            range(1, simulation_config.n_trees + 1),
            simulation_config.n_horizontal_edges,
            range(1, simulation_config.n_replicas + 1),
        )
    )
    for param, treenum, n_horizontal, replica in track(
        expected_simulated_datasets, description="Simulating datasets..."
    ):
        registry_key = {
            "poly_level": param.poly,
            "character_count": param.n_chars,
            "min_tree_height": param.tree_height,
            "homoplasy_factor": param.homoplasy_factor,
            "horizontal_edges": n_horizontal,
            "model_tree": treenum,
            "replica": replica,
        }
        output_dir = (
            sim_data_dir
            / f"{param.poly}_{param.homoplasy_factor}_{param.tree_height}_{param.n_chars}"
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"sim_{n_horizontal}_{treenum}_{replica}.csv"
        config_path = param_and_borrowing_to_config[(param, n_horizontal > 0)]
        seed = stable_hash_dict(registry_key)
        arglist = [
            "java",
            "-jar",
            "bin/LingPhyloSimulator.jar",
            "--simulate",
            # input config
            "--sim-params-file",
            str(config_path),
            # output file
            "--sim-output-file",
            str(output_path),
            "--sim-char-class",
            "PolymorphicCharacterClass",
            "--seed",
            str(seed),
            "--no-print",
        ]
        if n_horizontal == 0:
            arglist.append("--tree")
            tree_file_path = horedge_treenum_to_path[(n_horizontal, treenum)]
            with open(tree_file_path) as tree_file:
                tree_newick = tree_file.read().strip()
            arglist.append(tree_newick)
        else:
            arglist.append("--network-input-file")
            arglist.append(str(horedge_treenum_to_path[(n_horizontal, treenum)]))
        subprocess.run(args=arglist)
        sim_data_registry.append(
            {
                **registry_key,
                "path": str(output_path),
            }
        )
    sim_data_registry_pl = pl.DataFrame(
        data=sim_data_registry, schema=SIMULATED_DATA_REGISTRY_SCHEMA
    )
    sim_data_registry_pl.write_csv(e_folder / "simulated_data_registry.csv")
    print(f"Simulated {len(sim_data_registry)} datasets.")
