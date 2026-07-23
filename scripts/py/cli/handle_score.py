"""`pch experiment score` — RF-score inference point estimates against model truth.

Separate from inference (which is source-agnostic): scoring needs the simulated
model tree, which real datasets lack. Joins the inference registry to
simulated_data_registry on dataset_id == path to recover model_tree, resolves the
base tree, scores each point estimate, and writes inference_data/scores.csv.

Incremental + idempotent: an already-scored (dataset_id, method, config_hash) is
kept as-is, so re-running only scores new entries.
"""

from pathlib import Path

import polars as pl
from rich import print

from scripts.lib.experiment import ExperimentConfig
from scripts.lib.inference import registry
from scripts.lib.inference.scoring import resolve_reference_newick, score
from scripts.py.cli.schemata import (
    INFERENCE_REGISTRY_SCHEMA,
    SCORES_SCHEMA,
    SIMULATED_DATA_REGISTRY_SCHEMA,
)


def handle_score(config: ExperimentConfig) -> Path:
    experiment_folder = config.experiment_folder
    inf_csv = registry.registry_path(experiment_folder)
    assert inf_csv.exists(), (
        f"No inference registry at {inf_csv}. Run `pch experiment inference` first."
    )
    sim_csv = experiment_folder / "simulation_data" / "simulated_data_registry.csv"
    assert sim_csv.exists(), f"No simulation registry at {sim_csv}."
    out = experiment_folder / "inference_data" / "scores.csv"

    # Keep already-scored rows; only score the rest (resume, like inference).
    existing = (
        pl.read_csv(out, schema=SCORES_SCHEMA)
        if out.exists()
        else pl.DataFrame(schema=SCORES_SCHEMA)
    )
    already = {
        (r["dataset_id"], r["method"], r["config_hash"])
        for r in existing.iter_rows(named=True)
    }

    inf = pl.read_csv(inf_csv, schema=INFERENCE_REGISTRY_SCHEMA)
    # Canonicalize sim `path` to match the stored (canonical) dataset_id.
    sim = pl.read_csv(sim_csv, schema=SIMULATED_DATA_REGISTRY_SCHEMA).select(
        pl.col("path").map_elements(registry.canonical_path, return_dtype=pl.String),
        "model_tree",
    )
    joined = inf.join(sim, left_on="dataset_id", right_on="path")

    # TODO: parallelize — scoring is independent per row but runs sequentially,
    # so a full pass is one Rscript subprocess per estimate (~2s each, hours at
    # experiment scale). Fan out with a process pool (resolve_reference_newick's
    # lru_cache is per-process, so re-warm or share refs across workers).
    new: list[dict[str, object]] = []
    for r in joined.iter_rows(named=True):
        key = (r["dataset_id"], r["method"], r["config_hash"])
        if key in already or not r["point_estimate_newick"] or r["model_tree"] is None:
            continue
        try:
            ref = resolve_reference_newick(experiment_folder, r["model_tree"])
            sr = score(r["point_estimate_newick"], ref)
        except Exception as e:  # noqa: BLE001 — one bad score must not abort the pass
            print(f"[yellow]Scoring failed for {r['dataset_id']}: {e}[/yellow]")
            continue
        new.append(
            {
                "dataset_id": r["dataset_id"],
                "method": r["method"],
                "config_hash": r["config_hash"],
                "fn_rate": sr.fn_rate,
                "fp_rate": sr.fp_rate,
            }
        )
        already.add(key)  # dedup within this run: a duplicate sim `path` row
        # fans the join out, so guard against re-scoring the same key twice.

    out.parent.mkdir(parents=True, exist_ok=True)
    pl.concat([existing, pl.DataFrame(new, schema=SCORES_SCHEMA)]).write_csv(out)
    return out
