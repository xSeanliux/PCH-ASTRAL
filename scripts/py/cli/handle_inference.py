"""Inference pipeline: sim registry → api.infer per (dataset, method) → compact."""

from pathlib import Path

import polars as pl
from rich import print

from scripts.lib.experiment import ExperimentConfig, MethodConfig
from scripts.lib.inference import api, registry
from scripts.lib.inference.inference import TreeInferenceMethod
from scripts.lib.inference.methods import resolve_config
from scripts.lib.types import Polymorphism


def select_methods(methods: MethodConfig) -> list[TreeInferenceMethod]:
    # M1: only MP4 is wired.
    return [TreeInferenceMethod.MP] if methods.mp4 is not None else []


def handle_inference(config: ExperimentConfig) -> Path:
    experiment_folder = config.experiment_folder
    sim_registry = experiment_folder / "simulation_data" / "simulated_data_registry.csv"
    assert sim_registry.exists(), (
        f"No simulation registry at {sim_registry}. Run `pch simulation` first."
    )

    methods = select_methods(config.methods)
    inference_dir = experiment_folder / "inference_data"
    parts_dir = inference_dir / ".parts"
    parts_dir.mkdir(parents=True, exist_ok=True)

    registry.init_manifest(experiment_folder, [m.value for m in methods])

    n_runs = 0
    rows = pl.read_csv(sim_registry).iter_rows(named=True)
    for row in rows:
        for method in methods:
            out_dir = inference_dir / Path(row["path"]).parent.name
            result = api.infer(
                Path(row["path"]), out_dir, method, resolve_config(method, None)
            )
            # Stamp the simulation join keys from the sim-registry row.
            result.poly = Polymorphism(row["poly_level"])
            result.homoplasy_factor = row["homoplasy_factor"]
            result.tree_height = row["min_tree_height"]
            result.n_chars = row["character_count"]
            result.ret_edges = row["horizontal_edges"]
            result.target_tree = row["model_tree"]
            result.replica = row["replica"]
            registry.write_part(result, parts_dir)
            n_runs += 1

    registry.finalize_manifest(experiment_folder, n_runs)
    out = registry.compact(experiment_folder)
    print(f"Wrote {n_runs} inference rows to [green]{out}[/green].")
    return out
