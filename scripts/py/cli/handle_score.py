"""`pch experiment score` — RF-score inference point estimates against model truth.

Separate from inference (which is source-agnostic): scoring needs the simulated
model tree, which real datasets lack. Joins the inference registry to
simulated_data_registry on dataset_id == path to recover model_tree, resolves the
base tree, scores each point estimate, and writes inference_data/scores.csv.

Incremental + idempotent: an already-scored (dataset_id, method, config_hash) is
kept as-is, so re-running only scores new entries.

Scoring is one `Rscript` subprocess per estimate, so it is I/O-bound, not
GIL-bound: a thread pool (`threads=`) gives near-linear speedup and keeps
`resolve_reference_newick`'s cache shared, which a process pool would not.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import polars as pl
from rich import print
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TimeRemainingColumn

from scripts.lib.experiment import ExperimentConfig
from scripts.lib.inference import registry
from scripts.lib.inference.scoring import resolve_reference_newick, score
from scripts.py.cli.schemata import (
    INFERENCE_REGISTRY_SCHEMA,
    SCORES_SCHEMA,
    SIMULATED_DATA_REGISTRY_SCHEMA,
)

type Row = dict[str, object]


@dataclass(frozen=True)
class _Task:
    """One estimate to score — typed, so workers never touch untyped CSV rows."""

    dataset_id: str
    method: str
    config_hash: str
    model_tree: int
    estimate_newick: str


def handle_score(config: ExperimentConfig, threads: int = 1) -> Path:
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

    # Select first, score second. Dedup must happen before the fan-out: a
    # duplicate sim `path` row fans the join out, and concurrent workers would
    # race the `already` set and re-score the same key twice.
    todo: list[_Task] = []
    for r in joined.iter_rows(named=True):
        key = (r["dataset_id"], r["method"], r["config_hash"])
        if key in already or not r["point_estimate_newick"] or r["model_tree"] is None:
            continue
        already.add(key)
        todo.append(
            _Task(
                dataset_id=r["dataset_id"],
                method=r["method"],
                config_hash=r["config_hash"],
                model_tree=r["model_tree"],
                estimate_newick=r["point_estimate_newick"],
            )
        )

    def score_row(t: _Task) -> Row | None:
        try:
            ref = resolve_reference_newick(experiment_folder, t.model_tree)
            sr = score(t.estimate_newick, ref)
        except Exception as e:  # noqa: BLE001 — one bad score must not abort the pass
            print(f"[yellow]Scoring failed for {t.dataset_id}: {e}[/yellow]")
            return None
        return {
            "dataset_id": t.dataset_id,
            "method": t.method,
            "config_hash": t.config_hash,
            "fn_rate": sr.fn_rate,
            "fp_rate": sr.fp_rate,
        }

    new: list[Row] = []
    if todo:
        # A full pass is thousands of ~2s subprocesses; show progress so a long
        # run is distinguishable from a hung one.
        with Progress(
            *Progress.get_default_columns()[:1],
            BarColumn(),
            MofNCompleteColumn(),
            TimeRemainingColumn(),
            transient=True,
        ) as progress:
            task = progress.add_task(f"Scoring ({threads} thread(s))", total=len(todo))

            def tracked(t: _Task) -> Row | None:
                result = score_row(t)
                progress.advance(task)
                return result

            if threads > 1:
                with ThreadPoolExecutor(max_workers=threads) as pool:
                    scored = list(pool.map(tracked, todo))  # map preserves input order
            else:
                scored = [tracked(t) for t in todo]
        new = [s for s in scored if s is not None]

    out.parent.mkdir(parents=True, exist_ok=True)
    # Write-then-rename: scores.csv is rewritten wholesale (existing + new), so a
    # crash mid-write would otherwise truncate away already-scored rows. os.replace
    # is atomic within a filesystem, so readers see either the old file or the new.
    tmp = out.with_suffix(".csv.tmp")
    pl.concat([existing, pl.DataFrame(new, schema=SCORES_SCHEMA)]).write_csv(tmp)
    os.replace(tmp, out)
    return out
