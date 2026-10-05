from scripts.lib.experiment import (
    ExperimentConfig,
    ExperimentSimulationConfig,
    SimulationParamSetting,
)
from scripts.lib.simulation.outgroup import draw_lengths, graft_network, graft_tree
from scripts.lib.simulation.types import SimulationConfigFactory
from scripts.py.cli.schemata import (
    CONFIG_REGISTRY_SCHEMA,
    MODEL_GRAPH_REGISTRY,
    SIMULATED_DATA_REGISTRY_SCHEMA,
)
from itertools import product
from rich import print
from rich.progress import track
from pathlib import Path
import polars as pl
from hashlib import sha256
from typing import Any, NamedTuple, TypedDict
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


class Graft(NamedTuple):
    outgroup_label: str
    seed: int
    stem_len: float
    og_len: float


class ModelGraphRow(TypedDict):
    """One model_graph_registry.csv row: a base tree or network in the experiment."""

    horizontal_edges: int
    model_tree: int
    path: str
    outgroup_label: str | None
    outgroup_seed: int | None
    outgroup_branch_length: float | None
    ingroup_stem_length: float | None


def copy_model_graphs(
    simulation_config: ExperimentSimulationConfig, e_folder: Path
) -> list[ModelGraphRow]:
    """Write every base tree and network into the experiment folder, grafting the
    outgroup when one is configured, and return their registry rows."""
    n_trees = simulation_config.n_trees

    def graft_of(model_tree: int) -> Graft | None:
        # Seeded on the model tree alone: a base tree is shared across every h,
        # so each keeps one outgroup geometry.
        if simulation_config.outgroup_label is None:
            return None
        seed = stable_hash_dict({"model_tree": model_tree})
        return Graft(simulation_config.outgroup_label, seed, *draw_lengths(seed))

    def row(h: int, model_tree: int, path: Path) -> ModelGraphRow:
        graft = graft_of(model_tree)
        return {
            "horizontal_edges": h,
            "model_tree": model_tree,
            "path": str(path),
            "outgroup_label": graft.outgroup_label if graft else None,
            "outgroup_seed": graft.seed if graft else None,
            "ingroup_stem_length": graft.stem_len if graft else None,
            "outgroup_branch_length": graft.og_len if graft else None,
        }

    rows: list[ModelGraphRow] = []

    # Base trees, whether or not h = 0 is simulated: they are the reference for
    # every dataset built on them.
    trees = simulation_config.base_trees_file.read_text().splitlines(keepends=True)
    assert len(trees) >= n_trees, f"Wanted {n_trees} but only found {len(trees)} trees."
    for i, tree in enumerate(trees[:n_trees], 1):
        graft = graft_of(i)
        if graft:
            tree = (
                graft_tree(tree, graft.outgroup_label, graft.stem_len, graft.og_len)
                + "\n"
            )
        path = e_folder / f"model_tree_{i}.txt"
        path.write_text(tree)
        rows.append(row(0, i, path))
    print(f"Copied {n_trees} trees over to {_format_path(e_folder)}.")

    network_folder = e_folder / "model_networks"
    network_folder.mkdir(parents=True, exist_ok=True)
    networks = [
        (h, i)
        for h in simulation_config.n_horizontal_edges
        for i in range(1, n_trees + 1)
        if h != 0
    ]
    for h, i in track(networks, description="Copying model networks..."):
        source = simulation_config.base_networks_dir / f"net{h}-{i}.txt"
        assert source.is_file(), f"No network at {source}."
        network = source.read_text()
        graft = graft_of(i)
        if graft:
            lines = graft_network(
                network.splitlines(), graft.outgroup_label, graft.stem_len, graft.og_len
            )
            network = "\n".join(lines) + "\n"
        # Register the copy, not the source: the copy is what gets simulated.
        path = network_folder / source.name
        path.write_text(network)
        rows.append(row(h, i, path))
    print(f"Copied {len(networks)} networks over to {_format_path(network_folder)}.")
    return rows


def handle_simulation(config: ExperimentConfig):

    simulation_config = config.simulation
    e_folder = config.experiment_folder / "simulation_data"
    print(f"Creating output folder at {_format_path(str(e_folder))}")
    e_folder.mkdir(parents=True, exist_ok=True)

    model_graph_registry = copy_model_graphs(simulation_config, e_folder)
    pl.DataFrame(data=model_graph_registry, schema=MODEL_GRAPH_REGISTRY).write_csv(
        e_folder / "model_graph_registry.csv"
    )
    horedge_treenum_to_path: dict[tuple[int, int], str] = {
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
