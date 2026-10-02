"""Status report: expected vs done inference runs for an experiment."""

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

import polars as pl
from rich import print

from scripts.lib.experiment import ExperimentConfig
from scripts.lib.inference import registry, scheduler
from scripts.lib.model.methods import InferenceMethod
from scripts.lib.inference.scheduler import DatasetKey
from scripts.lib.inference.method_config import config_hash
from scripts.py.cli.handle_inference import select_runners
from scripts.py.cli.schemata import SIMULATED_DATA_REGISTRY_SCHEMA

_MISSING_CAP = 10

# (condition, label) -> (done_count, expected_count). A label is the method's
# value, or `<method>.<suffix>` for each run of a method that fans out.
StatusCounts = dict[tuple[str, str], tuple[int, int]]
# (condition, label) -> [dataset stems not yet done]
MissingMap = dict[tuple[str, str], list[str]]
# method -> [(suffix, config_hash)], one per run of a method that fans out
FanOut = Mapping[InferenceMethod, Sequence[tuple[str, str]]]


def fan_out(config: ExperimentConfig, methods: Sequence[InferenceMethod]) -> FanOut:
    """The methods that run more than once per dataset, with each run's identity."""
    runners = select_runners(config.methods)
    out: dict[InferenceMethod, list[tuple[str, str]]] = {}
    for m in methods:
        runs = [
            (r.suffix, config_hash(r.config))
            for r in runners
            if r.method is m and r.suffix
        ]
        if runs:
            out[m] = runs
    return out


def labels(methods: Sequence[InferenceMethod], fans: FanOut) -> list[str]:
    return [
        label
        for m in methods
        for label in (
            [f"{m.value}.{s}" for s, _ in fans[m]] if m in fans else [m.value]
        )
    ]


def compute_status(
    sim_rows: Iterable[Mapping[str, str | int | float]],
    methods: Sequence[InferenceMethod],
    done: dict[DatasetKey, set[tuple[str, str]]],
    fans: FanOut | None = None,
) -> tuple[StatusCounts, MissingMap]:
    """Count done/expected per (condition, label); collect missing stems.

    Pure — no I/O. Condition = parent dir name of each sim row's path.
    A method is done for a dataset if it appears (any config_hash) in `done`. A
    method in `fans` is counted per run, each done only under its own config_hash.
    """
    fans = fans or {}
    expected: dict[tuple[str, str], int] = defaultdict(int)
    n_done: dict[tuple[str, str], int] = defaultdict(int)
    missing: MissingMap = defaultdict(list)

    for row in sim_rows:
        path = str(row["path"])
        condition = Path(path).parent.name
        dataset_id = registry.canonical_path(path)
        dkey = (dataset_id,)
        ok_runs = done.get(dkey, set())
        ok_methods = {m for m, _ in ok_runs}
        stem = Path(path).stem

        for method in methods:
            if method in fans:
                units = [
                    (f"{method.value}.{s}", (method.value, h) in ok_runs)
                    for s, h in fans[method]
                ]
            else:
                units = [(method.value, method.value in ok_methods)]
            for label, is_done in units:
                key = (condition, label)
                expected[key] += 1
                if is_done:
                    n_done[key] += 1
                else:
                    missing[key].append(stem)

    counts: StatusCounts = {k: (n_done.get(k, 0), v) for k, v in expected.items()}
    return counts, dict(missing)


def _status_from_registry(config: ExperimentConfig) -> None:
    """Real-data fallback: no sim registry ⇒ no expected count, so just tally the
    inference registry's recorded runs per method (reads registry ∪ shards)."""
    done = scheduler.completed_runs(config.experiment_folder)
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

    methods = list(dict.fromkeys(r.method for r in select_runners(config.methods)))
    if not methods:
        print("[yellow]No methods enabled in config.[/yellow]")
        return

    rows = list(
        pl.read_csv(sim_registry, schema=SIMULATED_DATA_REGISTRY_SCHEMA).iter_rows(
            named=True
        )
    )
    done = scheduler.completed_runs(config.experiment_folder)
    fans = fan_out(config, methods)
    counts, missing = compute_status(rows, methods, done, fans)

    # Unique conditions in insertion order
    conditions: dict[str, None] = {}
    for cond, _ in counts:
        conditions[cond] = None

    method_values = labels(methods, fans)
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
