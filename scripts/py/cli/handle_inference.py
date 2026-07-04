"""Inference pipeline: sim registry → dependency-scheduled runs → registry.

Each enabled method runs per dataset in dependency order. The registry records
only SUCCESSFUL results (the analyzable ledger): already-done work is skipped
(resume), runs blocked on a missing dependency are logged, failures are logged
(their `log_path` has the details). See docs/ARCHITECTURE.md.
"""

from pathlib import Path

import polars as pl
from rich import print

from scripts.lib.experiment import ExperimentConfig, MethodConfig
from scripts.lib.inference import api, registry, scheduler
from scripts.lib.inference.inference import RunStatus, TreeInferenceMethod
from scripts.lib.inference.method_config import config_for, config_hash
from scripts.lib.inference.runners import RUNNERS
from scripts.lib.inference.scoring import resolve_reference_newick, score
from scripts.lib.types import Polymorphism
from scripts.py.cli.schemata import SIMULATED_DATA_REGISTRY_SCHEMA


def select_methods(methods: MethodConfig) -> list[TreeInferenceMethod]:
    # Enabled = a config of the method's type is present (matched by class).
    # Ordered so dependencies run first; a dependency enabled elsewhere / in a
    # prior run is handled at run time by the scheduler's registry gate.
    enabled = [m for m in RUNNERS if config_for(methods, m) is not None]
    deps_of = {}
    for m in enabled:
        cfg = config_for(methods, m)
        assert cfg is not None  # enabled ⇒ present
        deps_of[m] = RUNNERS[m].dependencies(cfg)
    return scheduler.topological_order(enabled, deps_of)


def _dataset_keys(row: dict[str, object]) -> dict[str, object]:
    """The join-key columns for a sim-registry row (dataset_id from its path)."""
    return {
        "dataset_id": Path(str(row["path"])).stem,
        "poly_level": row["poly_level"],
        "character_count": row["character_count"],
        "min_tree_height": row["min_tree_height"],
        "homoplasy_factor": row["homoplasy_factor"],
        "horizontal_edges": row["horizontal_edges"],
        "model_tree": row["model_tree"],
        "replica": row["replica"],
    }


def handle_inference(config: ExperimentConfig) -> Path:
    experiment_folder = config.experiment_folder
    sim_registry = experiment_folder / "simulation_data" / "simulated_data_registry.csv"
    assert sim_registry.exists(), (
        f"No simulation registry at {sim_registry}. Run `pch simulation` first."
    )

    methods = select_methods(config.methods)
    assert methods, (
        "No runnable inference methods selected — the config enables none that this "
        "milestone supports (MP4/GA/ASTRAL3). Nothing to do."
    )
    inference_dir = experiment_folder / "inference_data"
    registry.init_manifest(experiment_folder, [m.value for m in methods])

    ledger = scheduler.Ledger(experiment_folder)
    tally = {"ok": 0, "skipped": 0, "blocked": 0, "failed": 0}
    rows = pl.read_csv(sim_registry, schema=SIMULATED_DATA_REGISTRY_SCHEMA).iter_rows(
        named=True
    )
    for row in rows:
        keys = _dataset_keys(row)
        dkey = scheduler.dataset_key(keys)
        out_dir = inference_dir / Path(str(row["path"])).parent.name
        for method in methods:
            cfg = config_for(config.methods, method)
            assert cfg is not None  # select_methods only yields enabled methods

            if ledger.already_done(keys, method, config_hash(cfg)):
                ledger.mark_ok(dkey, method)  # its dependents still see it satisfied
                tally["skipped"] += 1
                continue

            unmet = ledger.unmet_dependencies(dkey, RUNNERS[method].dependencies(cfg))
            if unmet:
                need = ", ".join(d.value for d in unmet)
                print(
                    f"[yellow]{method.value} blocked on {keys['dataset_id']}: "
                    f"missing {need}[/yellow]"
                )
                tally["blocked"] += 1
                continue

            result = api.infer(Path(str(row["path"])), out_dir, method, cfg)
            if result.status is not RunStatus.OK:
                # Not analyzable → not in the registry; the log has the details.
                print(
                    f"[yellow]{method.value} failed on {keys['dataset_id']} "
                    f"(see {result.log_path})[/yellow]"
                )
                tally["failed"] += 1
                continue

            # Success: stamp the sim join keys, RF-score, record.
            result.poly = Polymorphism(str(row["poly_level"]))
            result.homoplasy_factor = row["homoplasy_factor"]
            result.tree_height = row["min_tree_height"]
            result.n_chars = row["character_count"]
            result.ret_edges = row["horizontal_edges"]
            result.target_tree = row["model_tree"]
            result.replica = row["replica"]
            if result.target_tree is not None:
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
            ledger.mark_ok(dkey, method)
            tally["ok"] += 1

    registry.finalize_manifest(experiment_folder, tally["ok"])
    out = registry.compact(experiment_folder)
    print(
        f"Inference: {tally['ok']} ok, {tally['skipped']} skipped, "
        f"{tally['blocked']} blocked, {tally['failed']} failed → [green]{out}[/green]."
    )
    return out
