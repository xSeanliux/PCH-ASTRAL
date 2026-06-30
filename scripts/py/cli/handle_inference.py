"""Inference pipeline: sim registry → api.infer per (dataset, method) → compact."""

from pathlib import Path

import polars as pl
from pydantic import BaseModel
from rich import print

from scripts.lib.experiment import ASTRAL3Config, ExperimentConfig, MethodConfig
from scripts.lib.inference import api, registry
from scripts.lib.inference.inference import (
    RunStatus,
    TreeInferenceMethod,
)
from scripts.lib.inference.scoring import resolve_reference_newick, score
from scripts.lib.types import Polymorphism
from scripts.py.cli.schemata import SIMULATED_DATA_REGISTRY_SCHEMA

# Single source of truth: (method, MethodConfig attr) in dependency order —
# MP4 and GA before ASTRAL3 (which needs their bipartitions).
_METHOD_FIELDS: list[tuple[TreeInferenceMethod, str]] = [
    (TreeInferenceMethod.MP, "mp4"),
    (TreeInferenceMethod.GA, "gray_atkinson"),
    (TreeInferenceMethod.PCH_ASTRAL3, "astral_3"),
]


# Heuristic ASTRAL3 bipartition strategy → the upstream method that produces it.
_STRATEGY_METHOD = {
    ASTRAL3Config.BipartitionStrategy.MP4_TREES: TreeInferenceMethod.MP,
    ASTRAL3Config.BipartitionStrategy.GA_TREES: TreeInferenceMethod.GA,
}


def _astral3_required_methods(a3: ASTRAL3Config) -> set[TreeInferenceMethod]:
    if a3.is_exact:
        return set()
    return {_STRATEGY_METHOD[s] for s in a3.effective_strategies}


def select_methods(methods: MethodConfig) -> list[TreeInferenceMethod]:
    a3 = methods.astral_3
    if a3 is not None:
        attr_of = {m: attr for m, attr in _METHOD_FIELDS}
        missing = [
            attr_of[m]
            for m in _astral3_required_methods(a3)
            if getattr(methods, attr_of[m]) is None
        ]
        if missing:
            strategies = [s.value for s in a3.effective_strategies]
            raise ValueError(
                f"pch_astral3 (heuristic, strategies={strategies}) requires: "
                + ", ".join(sorted(missing))
            )
    return [m for m, attr in _METHOD_FIELDS if getattr(methods, attr) is not None]


def pipeline_config(methods: MethodConfig, m: TreeInferenceMethod) -> BaseModel:
    config = getattr(methods, dict(_METHOD_FIELDS)[m])
    if config is None:  # select_methods only yields enabled methods — guard anyway.
        raise ValueError(f"No config for selected method {m.value}")
    return config


def _astral3_upstream_failed(
    methods: MethodConfig,
    method: TreeInferenceMethod,
    statuses: dict[TreeInferenceMethod, RunStatus],
) -> bool:
    # Heuristic ASTRAL3 needs its selected bipartitions from THIS run (not stale files).
    a3 = methods.astral_3
    if method is not TreeInferenceMethod.PCH_ASTRAL3 or a3 is None:
        return False
    return any(
        statuses.get(m) is not RunStatus.OK for m in _astral3_required_methods(a3)
    )


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
            if _astral3_upstream_failed(config.methods, method, statuses):
                result = api.failed_result(
                    Path(row["path"]).stem,
                    out_dir,
                    method,
                    pipeline_config(config.methods, method),
                    "upstream MP4/GA failed or absent this run",
                )
            else:
                result = api.infer(
                    Path(row["path"]),
                    out_dir,
                    method,
                    pipeline_config(config.methods, method),
                )
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
