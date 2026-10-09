"""`pch experiment network-score` — CmpNets each network family row against its
reference network.

Reads each network run's family CSV (`group_estimate_path` in inference_registry),
joins simulated_data_registry on dataset_id == path for (horizontal_edges,
model_tree), writes inference_data/network_scores.csv. A key
already in the file is kept, failed and timed-out rows included: a slow network
stays visible and is not retried every run. Never touches inference rows.
"""

import subprocess
import time
from pathlib import Path

import polars as pl
from rich import print

from scripts.lib.experiment import CamusConfig, ExperimentConfig
from scripts.lib.inference import registry
from scripts.lib.inference.registry import Cell
from scripts.lib.inference.scoring import (
    PHYLONET_JAR,
    score_network,
    resolve_reference_network,
)
from scripts.lib.model.methods import NetworkInferenceMethod, RunStatus
from scripts.py.cli.schemata import (
    INFERENCE_REGISTRY_SCHEMA,
    NETWORK_FAMILY_SCHEMA,
    NETWORK_SCORES_SCHEMA,
    SIMULATED_DATA_REGISTRY_SCHEMA,
)

KEY_COLUMNS = ["dataset_id", "method", "config_hash", "edges_added"]


def read_families(experiment_folder: Path) -> pl.DataFrame:
    """One row per network: every registered run's family, tagged with its run.

    :raises AssertionError: if no network run is registered.
    """
    path = registry.registry_path(experiment_folder)
    runs = (
        pl.read_csv(path, schema=INFERENCE_REGISTRY_SCHEMA)
        if path.exists()
        else pl.DataFrame(schema=INFERENCE_REGISTRY_SCHEMA)
    ).filter(
        pl.col("method").is_in([m.value for m in NetworkInferenceMethod])
        & (pl.col("status") == RunStatus.OK.value)  # failed runs wrote nothing
    )
    assert runs.height, (
        f"No network runs in {path}. Run `pch experiment inference` first."
    )
    families = []
    for r in runs.iter_rows(named=True):
        guide = None  # only CAMUS has one
        if r["method"] == NetworkInferenceMethod.CAMUS.value:
            config = CamusConfig.model_validate_json(r["method_config_json"])
            (guide,) = config.guide_trees
        family = pl.read_csv(
            r["group_estimate_path"],
            columns=list(NETWORK_FAMILY_SCHEMA),
            schema_overrides=NETWORK_FAMILY_SCHEMA,
        )
        families.append(
            family.with_columns(
                dataset_id=pl.lit(r["dataset_id"]),
                method=pl.lit(r["method"]),
                config_hash=pl.lit(r["config_hash"]),
                guide_tree=pl.lit(None if guide is None else str(guide), pl.String),
            )
        )
    return pl.concat(families)


def handle_network_score(config: ExperimentConfig) -> Path:
    """Score every unscored network family row and write network_scores.csv."""
    experiment_folder = config.experiment_folder
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
    already = {tuple(r[c] for c in KEY_COLUMNS) for r in existing.iter_rows(named=True)}

    fam = read_families(experiment_folder)
    sim = pl.read_csv(sim_csv, schema=SIMULATED_DATA_REGISTRY_SCHEMA).select(
        pl.col("path").map_elements(registry.canonical_path, return_dtype=pl.String),
        "horizontal_edges",
        "model_tree",
    )
    joined = fam.join(sim, left_on="dataset_id", right_on="path")

    new: list[dict[str, Cell]] = []
    try:
        for r in joined.iter_rows(named=True):
            key = tuple(r[c] for c in KEY_COLUMNS)
            # No reference yet: skip, so a later pass can score it (failures stick).
            if (
                key in already
                or not r["network_newick"]
                or r["model_tree"] is None
                or r["horizontal_edges"] is None
            ):
                continue
            already.add(key)  # a duplicate sim `path` row fans the join out
            row: dict[str, Cell] = {c: r[c] for c in KEY_COLUMNS} | {
                "guide_tree": r["guide_tree"]
            }
            label = (
                f"{r['dataset_id']} {r['guide_tree']} edges_added={r['edges_added']}"
            )
            t0 = time.perf_counter()
            try:
                ref = resolve_reference_network(
                    experiment_folder, r["horizontal_edges"], r["model_tree"]
                )
                s = score_network(r["network_newick"], ref)
                row |= {
                    "fn_rate": s.fn_rate,
                    "fp_rate": s.fp_rate,
                    "status": RunStatus.OK.value,
                }
            except subprocess.TimeoutExpired:
                row["status"] = RunStatus.TIMEOUT.value
                print(f"[yellow]Timed out: {label}[/yellow]")
            except Exception as e:  # noqa: BLE001 — one bad score must not abort the pass
                row["status"] = RunStatus.FAILED.value
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
