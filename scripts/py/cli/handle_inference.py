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
from scripts.py.cli.schemata import SIMULATED_DATA_REGISTRY_SCHEMA


def select_methods(methods: MethodConfig) -> list[TreeInferenceMethod]:
    # Enabled = a config of the method's type is present (matched by class).
    # Ordered so dependencies run first; a dependency enabled elsewhere / in a
    # prior run is handled at run time by the scheduler's registry gate.
    enabled = [m for m in RUNNERS if config_for(methods, m) is not None]
    deps_of: dict[TreeInferenceMethod, list[TreeInferenceMethod]] = {}
    for m in enabled:
        cfg = config_for(methods, m)
        assert cfg is not None  # enabled ⇒ present
        deps_of[m] = RUNNERS[m].dependencies(cfg)
    return scheduler.topological_order(enabled, deps_of)


def handle_inference(config: ExperimentConfig) -> Path:
    experiment_folder = config.experiment_folder
    sim_registry = experiment_folder / "simulation_data" / "simulated_data_registry.csv"
    assert sim_registry.exists(), (
        f"No simulation registry at {sim_registry}. Run `pch simulation` first."
    )

    methods = select_methods(config.methods)
    assert methods, (
        "No runnable inference methods selected — the config enables none that is supported. Noop. "
    )
    inference_dir = experiment_folder / "inference_data"
    registry.init_manifest(experiment_folder, [m.value for m in methods])

    done = scheduler.completed_runs(experiment_folder)  # {dataset → {(method, cfg)}}
    tally = {"ok": 0, "skipped": 0, "blocked": 0, "failed": 0}
    rows = pl.read_csv(sim_registry, schema=SIMULATED_DATA_REGISTRY_SCHEMA).iter_rows(
        named=True
    )
    for row in rows:
        input_path = Path(str(row["path"]))
        dataset_id = registry.canonical_path(input_path)  # identity = canonical path
        dkey = (dataset_id,)
        prior = done.get(dkey, set())
        ok_methods = {m for m, _ in prior}  # this dataset's OK methods; grows below
        out_dir = inference_dir / input_path.parent.name

        for method in methods:
            cfg = config_for(config.methods, method)
            assert cfg is not None  # select_methods only yields enabled methods
            ch = config_hash(cfg)

            if (method.value, ch) in prior:  # resume: this exact unit already done
                tally["skipped"] += 1
                continue

            unmet = [
                d
                for d in RUNNERS[method].dependencies(cfg)
                if d.value not in ok_methods
            ]
            if unmet:
                need = ", ".join(d.value for d in unmet)
                print(
                    f"[yellow]{method.value} blocked on {input_path.name}: "
                    f"missing {need}[/yellow]"
                )
                tally["blocked"] += 1
                continue

            result = api.infer(input_path, out_dir, method, cfg)
            if result.status is not RunStatus.OK:
                # Not analyzable → not in the registry; the log has the details.
                print(
                    f"[yellow]{method.value} failed on {input_path.name} "
                    f"(see {result.log_path})[/yellow]"
                )
                tally["failed"] += 1
                continue

            registry.write_result(result, experiment_folder)
            ok_methods.add(method.value)
            tally["ok"] += 1

    registry.finalize_manifest(experiment_folder, tally)
    out = registry.compact(experiment_folder)
    print(
        f"Inference: {tally['ok']} ok, {tally['skipped']} skipped, "
        f"{tally['blocked']} blocked, {tally['failed']} failed → [green]{out}[/green]."
    )
    return out
