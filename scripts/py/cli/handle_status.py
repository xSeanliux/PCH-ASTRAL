"""Status report: expected vs done inference runs for an experiment."""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path

import polars as pl
from rich import print

from scripts.lib.experiment import ExperimentConfig
from scripts.lib.inference import registry, scheduler
from scripts.lib.inference.inference import TreeInferenceMethod
from scripts.lib.inference.scheduler import DatasetKey
from scripts.py.cli.handle_inference import select_methods
from scripts.py.cli.schemata import SIMULATED_DATA_REGISTRY_SCHEMA

_MISSING_CAP = 10

# (condition, method_value) -> (done_count, expected_count)
StatusCounts = dict[tuple[str, str], tuple[int, int]]
# (condition, method_value) -> [dataset stems not yet done]
MissingMap = dict[tuple[str, str], list[str]]


def compute_status(
    sim_rows: Iterable[Mapping[str, str | int | float]],
    methods: list[TreeInferenceMethod],
    done: dict[DatasetKey, set[tuple[str, str]]],
) -> tuple[StatusCounts, MissingMap]:
    """Count done/expected per (condition, method); collect missing stems.

    Pure — no I/O. Condition = parent dir name of each sim row's path.
    A method is done for a dataset if it appears (any config_hash) in `done`.
    """
    expected: dict[tuple[str, str], int] = defaultdict(int)
    n_done: dict[tuple[str, str], int] = defaultdict(int)
    missing: MissingMap = defaultdict(list)

    for row in sim_rows:
        path = str(row["path"])
        condition = Path(path).parent.name
        dataset_id = registry.canonical_path(path)
        dkey = (dataset_id,)
        ok_methods = {m for m, _ in done.get(dkey, set())}
        stem = Path(path).stem

        for method in methods:
            key = (condition, method.value)
            expected[key] += 1
            if method.value in ok_methods:
                n_done[key] += 1
            else:
                missing[key].append(stem)

    counts: StatusCounts = {k: (n_done.get(k, 0), v) for k, v in expected.items()}
    return counts, dict(missing)


def handle_status(config: ExperimentConfig) -> None:
    """Print expected vs done per condition/method for an experiment."""
    sim_registry = (
        config.experiment_folder / "simulation_data" / "simulated_data_registry.csv"
    )
    if not sim_registry.exists():
        print(f"No simulation registry at [green]{sim_registry}[/green].")
        return

    methods = select_methods(config.methods)
    if not methods:
        print("[yellow]No methods enabled in config.[/yellow]")
        return

    rows = list(
        pl.read_csv(sim_registry, schema=SIMULATED_DATA_REGISTRY_SCHEMA).iter_rows(
            named=True
        )
    )
    done = scheduler.completed_runs(config.experiment_folder)
    counts, missing = compute_status(rows, methods, done)

    # Unique conditions in insertion order
    conditions: dict[str, None] = {}
    for cond, _ in counts:
        conditions[cond] = None

    method_values = [m.value for m in methods]
    total_done = total_expected = 0

    for cond in conditions:
        print(f"\n[bold]{cond}[/bold]")
        for mv in method_values:
            key = (cond, mv)
            d, e = counts.get(key, (0, 0))
            total_done += d
            total_expected += e
            print(f"  {mv}: {d}/{e}")
        for mv in method_values:
            stems = missing.get((cond, mv), [])
            if not stems:
                continue
            n = len(stems)
            shown = stems[:_MISSING_CAP]
            suffix = f" (+{n - _MISSING_CAP} more)" if n > _MISSING_CAP else ""
            print(f"  [yellow]missing {mv}:[/yellow] {', '.join(shown)}{suffix}")

    print(f"\n[bold]Total: {total_done}/{total_expected} done[/bold]")
