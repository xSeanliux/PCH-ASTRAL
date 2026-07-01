"""Inference pipeline: sim registry → api.infer per (dataset, method) → compact."""

from pathlib import Path

import polars as pl
from pydantic import BaseModel
from rich import print

from scripts.lib.experiment import ExperimentConfig, MethodConfig
from scripts.lib.inference import api, registry
from scripts.lib.inference.inference import (
    RunStatus,
    TreeInferenceMethod,
)
from scripts.lib.inference.runners import RUNNERS
from scripts.lib.inference.scoring import resolve_reference_newick, score
from scripts.lib.types import Polymorphism
from scripts.py.cli.schemata import SIMULATED_DATA_REGISTRY_SCHEMA

# Single source of truth: (method, MethodConfig attr). Order is the stable
# tiebreak for the topological sort below; real ordering comes from dependencies().
_METHOD_FIELDS: list[tuple[TreeInferenceMethod, str]] = [
    (TreeInferenceMethod.MP, "mp4"),
    (TreeInferenceMethod.GA, "gray_atkinson"),
    (TreeInferenceMethod.PCH_ASTRAL3, "astral_3"),
]


def pipeline_config(methods: MethodConfig, m: TreeInferenceMethod) -> BaseModel:
    config = getattr(methods, dict(_METHOD_FIELDS)[m])
    if config is None:  # select_methods only yields enabled methods — guard anyway.
        raise ValueError(f"No config for selected method {m.value}")
    return config


def _topological_order(
    enabled: list[TreeInferenceMethod], methods: MethodConfig
) -> list[TreeInferenceMethod]:
    # Kahn-style; stable by _METHOD_FIELDS order. Deps already known enabled.
    order = {m: i for i, (m, _) in enumerate(_METHOD_FIELDS)}
    enabled = sorted(enabled, key=lambda m: order[m])
    deps = {m: RUNNERS[m].dependencies(pipeline_config(methods, m)) for m in enabled}
    result: list[TreeInferenceMethod] = []
    while len(result) < len(enabled):
        ready = [
            m for m in enabled if m not in result and all(d in result for d in deps[m])
        ]
        if not ready:
            raise ValueError("dependency cycle among inference methods")
        result.extend(ready)
    return result


def select_methods(methods: MethodConfig) -> list[TreeInferenceMethod]:
    enabled = [m for m, attr in _METHOD_FIELDS if getattr(methods, attr) is not None]
    enabled_set = set(enabled)
    # Co-requisite: every dependency of an enabled method must also be enabled.
    for m in enabled:
        for dep in RUNNERS[m].dependencies(pipeline_config(methods, m)):
            if dep not in enabled_set:
                raise ValueError(f"{m.value} requires {dep.value} to be enabled")
    return _topological_order(enabled, methods)


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
        statuses: dict[TreeInferenceMethod, RunStatus] = {}
        for method in methods:
            out_dir = inference_dir / Path(row["path"]).parent.name
            cfg = pipeline_config(config.methods, method)
            # Dependencies must have succeeded THIS run (not stale files). A SLURM
            # launcher would instead await these deps — dependencies() is that hook.
            unmet = [
                d
                for d in RUNNERS[method].dependencies(cfg)
                if statuses.get(d) is not RunStatus.OK
            ]
            if unmet:
                result = api.failed_result(
                    Path(row["path"]).stem,
                    out_dir,
                    method,
                    cfg,
                    f"unmet dependencies: {', '.join(d.value for d in unmet)}",
                )
            else:
                result = api.infer(Path(row["path"]), out_dir, method, cfg)
            statuses[method] = result.status
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
