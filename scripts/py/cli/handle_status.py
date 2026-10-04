"""Status report: expected vs done inference runs for an experiment."""

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

import polars as pl
from rich import print

from scripts.lib.experiment import ExperimentConfig
from scripts.lib.inference import registry, scheduler
from scripts.lib.inference.scheduler import DatasetKey
from scripts.lib.inference.method_config import hash_config
from scripts.py.cli.handle_inference import select_runners
from scripts.py.cli.schemata import SIMULATED_DATA_REGISTRY_SCHEMA

_MISSING_CAP = 10

# (condition, label) -> (done_count, expected_count)
StatusCounts = dict[tuple[str, str], tuple[int, int]]
# (condition, label) -> [dataset stems not yet done]
MissingMap = dict[tuple[str, str], list[str]]
# One unit of work: (label, method value, config hash).
Unit = tuple[str, str, str]


def compute_status(
    sim_rows: Iterable[Mapping[str, str | int | float]],
    units: Sequence[Unit],
    done: dict[DatasetKey, set[tuple[str, str]]],
) -> tuple[StatusCounts, MissingMap]:
    """Count done/expected per (condition, label); collect missing stems.

    Pure, no I/O. Condition = parent dir name of each sim row's path.
    A unit is done for a dataset iff `(method, config_hash)` is in `done`.
    """
    expected: dict[tuple[str, str], int] = defaultdict(int)
    n_done: dict[tuple[str, str], int] = defaultdict(int)
    missing: MissingMap = defaultdict(list)

    for row in sim_rows:
        path = str(row["path"])
        condition = Path(path).parent.name
        ok_runs = done.get((registry.canonical_path(path),), set())
        stem = Path(path).stem

        for label, method, config_hash in units:
            key = (condition, label)
            expected[key] += 1
            if (method, config_hash) in ok_runs:
                n_done[key] += 1
            else:
                missing[key].append(stem)

    counts: StatusCounts = {k: (n_done.get(k, 0), v) for k, v in expected.items()}
    return counts, dict(missing)


def _status_from_registry(config: ExperimentConfig) -> None:
    """Real-data fallback: no sim registry ⇒ no expected count, so just tally the
    inference registry's recorded runs per method (reads registry ∪ shards)."""
    done = scheduler.get_completed_runs(config.experiment_folder)
    per_method: dict[str, int] = defaultdict(int)
    for methods_done in done.values():
        for method, _cfg in methods_done:
            per_method[method] += 1
    print(
        "[dim]No sim registry — per-method recorded runs (real-data experiment):[/dim]"
    )
    if not per_method:
        print("  [yellow]nothing recorded yet.[/yellow]")
        return
    for method in sorted(per_method):
        print(f"  {method}: {per_method[method]}")
    print(f"\n[bold]Total: {sum(per_method.values())} runs[/bold]")


def handle_status(config: ExperimentConfig) -> None:
    """Print expected vs done per condition/method for an experiment."""
    sim_registry = (
        config.experiment_folder / "simulation_data" / "simulated_data_registry.csv"
    )
    if not sim_registry.exists():
        # Real (non-simulated) experiments have no sim registry, so there's no
        # expected count — fall back to a per-method tally of what's recorded.
        _status_from_registry(config)
        return

    units = [
        (r.get_run_name(r.method.value), r.method.value, hash_config(r.config))
        for r in select_runners(config.methods)
    ]
    if not units:
        print("[yellow]No methods enabled in config.[/yellow]")
        return

    rows = list(
        pl.read_csv(sim_registry, schema=SIMULATED_DATA_REGISTRY_SCHEMA).iter_rows(
            named=True
        )
    )
    done = scheduler.get_completed_runs(config.experiment_folder)
    counts, missing = compute_status(rows, units, done)

    # Unique conditions in insertion order
    conditions: dict[str, None] = {}
    for cond, _ in counts:
        conditions[cond] = None

    labels = [label for label, _, _ in units]
    total_done = total_expected = 0

    for cond in conditions:
        print(f"\n[bold]{cond}[/bold]")
        for mv in labels:
            key = (cond, mv)
            d, e = counts.get(key, (0, 0))
            total_done += d
            total_expected += e
            print(f"  {mv}: {d}/{e}")
        for mv in labels:
            stems = missing.get((cond, mv), [])
            if not stems:
                continue
            n = len(stems)
            shown = stems[:_MISSING_CAP]
            suffix = f" (+{n - _MISSING_CAP} more)" if n > _MISSING_CAP else ""
            print(f"  [yellow]missing {mv}:[/yellow] {', '.join(shown)}{suffix}")

    print(f"\n[bold]Total: {total_done}/{total_expected} done[/bold]")
