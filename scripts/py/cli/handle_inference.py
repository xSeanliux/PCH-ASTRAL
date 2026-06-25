"""Inference pipeline: sim registry → api.infer per (dataset, method) → compact."""

from pathlib import Path

import polars as pl
from pydantic import BaseModel
from rich import print

from scripts.lib.experiment import ExperimentConfig, MethodConfig
from scripts.lib.inference import api, registry
from scripts.lib.inference.inference import TreeInferenceMethod
from scripts.lib.inference.scoring import resolve_reference_newick, score
from scripts.lib.types import Polymorphism
from scripts.py.cli.schemata import SIMULATED_DATA_REGISTRY_SCHEMA


def select_methods(methods: MethodConfig) -> list[TreeInferenceMethod]:
    # Dependency order: MP4 and GA before ASTRAL3 (its bipartition prereqs).
    selected: list[TreeInferenceMethod] = []
    if methods.mp4 is not None:
        selected.append(TreeInferenceMethod.MP)
    if methods.gray_atkinson is not None:
        selected.append(TreeInferenceMethod.GA)
    if methods.astral_3 is not None:
        selected.append(TreeInferenceMethod.PCH_ASTRAL3)
    return selected


def pipeline_config(methods: MethodConfig, m: TreeInferenceMethod) -> BaseModel:
    # Non-None because select_methods only included enabled methods.
    config = {
        TreeInferenceMethod.MP: methods.mp4,
        TreeInferenceMethod.GA: methods.gray_atkinson,
        TreeInferenceMethod.PCH_ASTRAL3: methods.astral_3,
    }[m]
    assert config is not None
    return config


def handle_inference(config: ExperimentConfig) -> Path:
    experiment_folder = config.experiment_folder
    sim_registry = experiment_folder / "simulation_data" / "simulated_data_registry.csv"
    assert sim_registry.exists(), (
        f"No simulation registry at {sim_registry}. Run `pch simulation` first."
    )

    methods = select_methods(config.methods)
    assert methods, (
        "No runnable inference methods selected — the config enables none that this "
        "milestone supports (M3 wires MP4/GA/ASTRAL3). Nothing to do."
    )
    inference_dir = experiment_folder / "inference_data"

    registry.init_manifest(experiment_folder, [m.value for m in methods])

    n_runs = 0
    rows = pl.read_csv(sim_registry, schema=SIMULATED_DATA_REGISTRY_SCHEMA).iter_rows(
        named=True
    )
    for row in rows:
        for method in methods:
            out_dir = inference_dir / Path(row["path"]).parent.name
            result = api.infer(
                Path(row["path"]),
                out_dir,
                method,
                pipeline_config(config.methods, method),
            )
            # Stamp the simulation join keys from the sim-registry row.
            result.poly = Polymorphism(row["poly_level"])
            result.homoplasy_factor = row["homoplasy_factor"]
            result.tree_height = row["min_tree_height"]
            result.n_chars = row["character_count"]
            result.ret_edges = row["horizontal_edges"]
            result.target_tree = row["model_tree"]
            result.replica = row["replica"]
            if result.target_tree is not None and result.point_estimate_newick:
                try:
                    ref = resolve_reference_newick(
                        experiment_folder, result.target_tree
                    )
                    sr = score(result.point_estimate_newick, ref)
                    result.fn_rate = sr.fn_rate
                    result.fp_rate = sr.fp_rate
                except Exception as e:  # noqa: BLE001 — one bad score must not abort
                    print(
                        f"[yellow]Scoring failed for {result.dataset_id}: {e}[/yellow]"
                    )
            registry.write_result(result, experiment_folder)
            n_runs += 1

    registry.finalize_manifest(experiment_folder, n_runs)
    out = registry.compact(experiment_folder)
    print(f"Wrote {n_runs} inference rows to [green]{out}[/green].")
    return out
