"""`pch experiment network-score` — CmpNets each network family row against its
reference network.

Reads camus_registry.csv, joins simulated_data_registry on dataset_id == path for
(horizontal_edges, model_tree), writes inference_data/network_scores.csv. A key
already in the file is kept, failed and timed-out rows included: a slow network
stays visible and is not retried every run. Never touches inference rows.
"""

import subprocess
import time
from pathlib import Path

import polars as pl
from rich import print

from scripts.lib.experiment import ExperimentConfig
from scripts.lib.inference import camus_registry, registry
from scripts.lib.inference.registry import Cell
from scripts.lib.inference.scoring import (
    PHYLONET_JAR,
    network_score,
    resolve_reference_network,
)
from scripts.py.cli.schemata import (
    CAMUS_REGISTRY_SCHEMA,
    NETWORK_SCORES_SCHEMA,
    SIMULATED_DATA_REGISTRY_SCHEMA,
)

KEY = ["dataset_id", "guide_tree", "config_hash", "k"]


def handle_network_score(config: ExperimentConfig) -> Path:
    experiment_folder = config.experiment_folder
    fam_csv = camus_registry.registry_path(experiment_folder)
    assert fam_csv.exists(), (
        f"No network family registry at {fam_csv}. Run `pch experiment inference` with camus first."
    )
    sim_csv = experiment_folder / "simulation_data" / "simulated_data_registry.csv"
    assert sim_csv.exists(), f"No simulation registry at {sim_csv}."
    # Failed rows are never retried, so a missing jar must not mark every key failed.
    assert PHYLONET_JAR.exists(), f"No {PHYLONET_JAR}; run `make install-phylonet`."
    out = experiment_folder / "inference_data" / "network_scores.csv"

    existing = (
        pl.read_csv(out, schema=NETWORK_SCORES_SCHEMA)
        if out.exists()
        else pl.DataFrame(schema=NETWORK_SCORES_SCHEMA)
    )
    already = {tuple(r[c] for c in KEY) for r in existing.iter_rows(named=True)}

    fam = pl.read_csv(fam_csv, schema=CAMUS_REGISTRY_SCHEMA)
    sim = pl.read_csv(sim_csv, schema=SIMULATED_DATA_REGISTRY_SCHEMA).select(
        pl.col("path").map_elements(registry.canonical_path, return_dtype=pl.String),
        "horizontal_edges",
        "model_tree",
    )
    joined = fam.join(sim, left_on="dataset_id", right_on="path")

    new: list[dict[str, Cell]] = []
    try:
        for r in joined.iter_rows(named=True):
            key = tuple(r[c] for c in KEY)
            if key in already or not r["network_newick"]:
                continue
            already.add(key)  # a duplicate sim `path` row fans the join out
            row: dict[str, Cell] = {c: r[c] for c in KEY} | {
                "fn": None,
                "fp": None,
                "avg": None,
            }
            label = f"{r['dataset_id']} {r['guide_tree']} k={r['k']}"
            t0 = time.perf_counter()
            try:
                ref = resolve_reference_network(
                    experiment_folder, r["horizontal_edges"], r["model_tree"]
                )
                s = network_score(r["network_newick"], ref)
                row |= {"fn": s.fn, "fp": s.fp, "avg": s.avg, "status": "ok"}
            except subprocess.TimeoutExpired:
                row["status"] = "timeout"
                print(f"[yellow]Timed out: {label}[/yellow]")
            except Exception as e:  # noqa: BLE001 — one bad score must not abort the pass
                row["status"] = "failed"
                print(f"[yellow]Scoring failed for {label}: {e}[/yellow]")
            row["runtime_seconds"] = time.perf_counter() - t0
            print(f"{row['status']} {label} in {row['runtime_seconds']:.1f}s")
            new.append(row)
    finally:
        # Calls can take hours: keep what was scored if the pass is killed.
        out.parent.mkdir(parents=True, exist_ok=True)
        pl.concat(
            [existing, pl.DataFrame(new, schema=NETWORK_SCORES_SCHEMA)]
        ).write_csv(out)
    return out
