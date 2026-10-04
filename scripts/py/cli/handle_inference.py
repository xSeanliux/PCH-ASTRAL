"""Inference pipeline: sim registry → dependency-scheduled runs → registry.

Each enabled method runs per dataset in dependency order. The registry records
only SUCCESSFUL results (the analyzable ledger): already-done work is skipped
(resume), runs blocked on a missing dependency are logged, failures are logged
(their `log_path` has the details). See docs/ARCHITECTURE.md.
"""

from collections.abc import Sequence
from pathlib import Path

import polars as pl
from rich import print

from scripts.lib.experiment import ExperimentConfig, MethodConfig
from scripts.lib.inference import api, registry, scheduler
from scripts.lib.model.methods import InferenceMethod, RunStatus
from scripts.lib.inference.method_config import hash_config
from scripts.lib.inference.runners import METHOD_TO_RUNNER_CLASS
from scripts.lib.inference.runners.base import Runner
from scripts.py.cli.schemata import SIMULATED_DATA_REGISTRY_SCHEMA


def map_method_to_dependencies(
    runners: Sequence[Runner],
) -> dict[InferenceMethod, list[InferenceMethod]]:
    """Each method's dependencies, unioned order-preserving across its runners.

    Two runners of one method (e.g. CAMUS's guides) may differ in dependencies;
    the method's scheduler node needs every edge.
    """
    method_to_dependencies: dict[InferenceMethod, list[InferenceMethod]] = {}
    for r in runners:
        method_to_dependencies[r.method] = list(
            dict.fromkeys(
                [*method_to_dependencies.get(r.method, []), *r.get_dependencies()]
            )
        )
    return method_to_dependencies


def select_runners(methods: MethodConfig) -> list[Runner]:
    """Every unit of work the config asks for, dependencies first."""
    runners = [r for cfg in methods.get_enabled_configs() for r in cfg.get_runners()]
    method_to_dependencies = map_method_to_dependencies(runners)
    # METHOD_TO_RUNNER_CLASS' insertion order is the canonical method order (fixed regardless of
    # which `methods:` fields are set); it's just the tie-break for independent
    # methods — sort_topologically still enforces real dependency edges.
    enabled = [m for m in METHOD_TO_RUNNER_CLASS if m in method_to_dependencies]
    order = scheduler.sort_topologically(enabled, method_to_dependencies)
    return sorted(runners, key=lambda r: order.index(r.method))


def handle_inference(
    config: ExperimentConfig,
    *,
    datasets: Path | None = None,
    method: str | None = None,
    no_compact: bool = False,
) -> Path:
    """Run enabled methods per dataset. SLURM batch knobs (all additive):
    `datasets` restricts to sim rows named in a paths file; `method` runs one
    enabled method; `no_compact` skips all manifest/compact (shard-only shards).
    """
    experiment_folder = config.experiment_folder
    sim_registry = experiment_folder / "simulation_data" / "simulated_data_registry.csv"
    assert sim_registry.exists(), (
        f"No simulation registry at {sim_registry}. Run `pch simulation` first."
    )

    runners = select_runners(config.methods)
    assert runners, (
        "No runnable inference methods selected — the config's `methods:` block enables "
        "none of the supported methods (mp4, gray_atkinson, astral_3, w_tree_qmc). Nothing to do."
    )
    if method is not None:  # SLURM: pin the run to one enabled method
        runners = [r for r in runners if method in (r.method.value, r.method.name)]
        assert runners, (
            f"Method {method!r} is not enabled in the config; "
            "cannot restrict the run to it."
        )
    inference_dir = experiment_folder / "inference_data"
    if not no_compact:
        registry.init_manifest(
            experiment_folder, list(dict.fromkeys(r.method.value for r in runners))
        )

    wanted = _read_dataset_filter(datasets)  # None = all rows
    done = scheduler.get_completed_runs(
        experiment_folder
    )  # {dataset → {(method, cfg)}}
    tally = {"ok": 0, "skipped": 0, "blocked": 0, "failed": 0}
    rows = pl.read_csv(sim_registry, schema=SIMULATED_DATA_REGISTRY_SCHEMA).iter_rows(
        named=True
    )
    for row in rows:
        input_path = Path(str(row["path"]))
        dataset_id = registry.canonical_path(input_path)  # identity = canonical path
        if wanted is not None and dataset_id not in wanted:
            continue  # SLURM: this shard doesn't own this dataset
        dkey = (dataset_id,)
        prior = done.get(dkey, set())
        ok_methods = {m for m, _ in prior}  # this dataset's OK methods; grows below
        out_dir = inference_dir / input_path.parent.name

        for r in runners:
            ch = hash_config(r.config)

            if (r.method.value, ch) in prior:  # resume: this exact unit already done
                tally["skipped"] += 1
                continue

            unmet = [d for d in r.get_dependencies() if d.value not in ok_methods]
            if unmet:
                need = ", ".join(d.value for d in unmet)
                print(
                    f"[yellow]{r.method.value} blocked on {input_path.name}: "
                    f"missing {need}[/yellow]"
                )
                tally["blocked"] += 1
                continue

            result = api.infer(input_path, out_dir, r)
            if result.status is not RunStatus.OK:
                # Not analyzable → not in the registry; the log has the details.
                print(
                    f"[yellow]{r.method.value} failed on {input_path.name} "
                    f"(see {result.log_path})[/yellow]"
                )
                tally["failed"] += 1
                continue

            registry.write_result(result, experiment_folder)
            ok_methods.add(r.method.value)
            tally["ok"] += 1

    if no_compact:  # SLURM batch: shards only; the compact job owns the manifest
        out = inference_dir / "inference_registry.csv"
    else:
        registry.finalize_manifest(experiment_folder, tally)
        out = registry.compact(experiment_folder)
    print(
        f"Inference: {tally['ok']} ok, {tally['skipped']} skipped, "
        f"{tally['blocked']} blocked, {tally['failed']} failed → [green]{out}[/green]."
    )
    return out


def _read_dataset_filter(datasets: Path | None) -> set[str] | None:
    """Paths file (one per line) → canonicalized set; None passes everything."""
    if datasets is None:
        return None
    lines = datasets.read_text().splitlines()
    # Canonicalize the STRIPPED line: a trailing space/`\r` would otherwise make a
    # path that never matches a stored dataset_id, silently dropping that dataset.
    return {registry.canonical_path(p.strip()) for p in lines if p.strip()}
