"""`pch experiment score` — RF-score inference point estimates against model truth.

Separate from inference (which is source-agnostic): scoring needs the simulated
model tree, which real datasets lack. Joins the inference registry to
simulated_data_registry on dataset_id == path to recover model_tree, resolves the
base tree, scores each point estimate, and writes inference_data/scores.csv.
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

    inf = pl.read_csv(inf_csv, schema=INFERENCE_REGISTRY_SCHEMA)
    sim = pl.read_csv(sim_csv, schema=SIMULATED_DATA_REGISTRY_SCHEMA)
    joined = inf.join(
        sim.select("path", "model_tree"), left_on="dataset_id", right_on="path"
    )

    scores: list[dict[str, object]] = []
    for r in joined.iter_rows(named=True):
        if not r["point_estimate_newick"] or r["model_tree"] is None:
            continue
        try:
            ref = resolve_reference_newick(experiment_folder, r["model_tree"])
            sr = score(r["point_estimate_newick"], ref)
        except Exception as e:  # noqa: BLE001 — one bad score must not abort the pass
            print(f"[yellow]Scoring failed for {r['dataset_id']}: {e}[/yellow]")
            continue
        scores.append(
            {
                "dataset_id": r["dataset_id"],
                "method": r["method"],
                "config_hash": r["config_hash"],
                "fn_rate": sr.fn_rate,
                "fp_rate": sr.fp_rate,
            }
        )

    out = experiment_folder / "inference_data" / "scores.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(scores, schema=SCORES_SCHEMA).write_csv(out)
    return out
