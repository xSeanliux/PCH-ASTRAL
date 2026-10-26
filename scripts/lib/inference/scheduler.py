"""Dependency-aware scheduling for the inference pipeline.

The registry holds only successful results, so a `(dataset, method, config_hash)`
row means that unit is done. `get_completed_runs` loads those into a lookup that
drives both **resume** (skip an exact already-done unit) and the **dependency
gate** (a method's output is available). Blocks/failures are logged by the
caller, never recorded. See docs/ARCHITECTURE.md.
"""

from collections import defaultdict, deque
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path

import polars as pl
from pydantic import ValidationError

from scripts.lib.inference import registry
from scripts.lib.inference.method_config import METHOD_TO_CONFIG_CLASS
from scripts.lib.inference.runners import METHOD_TO_RUNNER_CLASS
from scripts.lib.model.methods import InferenceMethod, RunStatus
from scripts.lib.inference.registry import Cell
from scripts.py.cli.schemata import INFERENCE_REGISTRY_SCHEMA

# A dataset's identity (its join-key values). `Cell` is defined in registry.
DatasetKey = tuple[Cell, ...]


def _add_ok_runs(
    rows: Iterable[Mapping[str, Cell]],
    done: dict[DatasetKey, set[tuple[str, str]]],
) -> None:
    """Fold status=="ok" rows into `done`, keyed by dataset in DATASET_KEY_COLUMNS
    order. Dedups naturally: the same run in both registry.csv and a shard yields
    one identical set entry. (dataset_id is a path string, so str() is a no-op that
    just aligns the two read paths' types.)
    """
    for row in rows:
        if row["status"] != RunStatus.OK.value:  # trust only successes
            continue
        key: DatasetKey = tuple(str(row[c]) for c in registry.DATASET_KEY_COLUMNS)
        done[key].add((str(row["method"]), str(row["config_hash"])))


def _iter_ok_rows(experiment_folder: Path) -> Iterator[Mapping[str, Cell]]:
    """status=="ok" rows of registry.csv, then of the shards."""
    out = registry.registry_path(experiment_folder)
    rows: Iterable[Mapping[str, Cell]] = []
    if out.exists():
        rows = pl.read_csv(out, schema=INFERENCE_REGISTRY_SCHEMA).iter_rows(named=True)
    for rs in (rows, registry._iter_shard_rows(experiment_folder)):
        yield from (r for r in rs if r["status"] == RunStatus.OK.value)


def get_completed_variants(
    experiment_folder: Path,
) -> dict[DatasetKey, set[tuple[str, str | None]]]:
    """`{dataset → {(method, run suffix)}}` for successful prior runs: the gate for
    `Runner.get_dependency_suffixes`. Rows whose config no longer parses are left out.
    """
    methods = {m.value: m for m in METHOD_TO_RUNNER_CLASS}
    done: dict[DatasetKey, set[tuple[str, str | None]]] = defaultdict(set)
    for row in _iter_ok_rows(experiment_folder):
        method = methods.get(str(row["method"]))
        if method is None:
            continue
        try:
            config = METHOD_TO_CONFIG_CLASS[method].model_validate_json(
                str(row["method_config_json"])
            )
        except ValidationError:
            continue
        key: DatasetKey = tuple(str(row[c]) for c in registry.DATASET_KEY_COLUMNS)
        done[key].add((method.value, METHOD_TO_RUNNER_CLASS[method](config).suffix))
    return dict(done)


def get_completed_runs(
    experiment_folder: Path,
) -> dict[DatasetKey, set[tuple[str, str]]]:
    """`{dataset → {(method, config_hash)}}` for successful prior runs.

    `(method, config_hash)` present ⇒ that exact unit is done (resume skip);
    the method present (any config) ⇒ its output is available (dependency gate).

    Reads the union of the compacted registry.csv AND the per-job shards. Under
    SLURM, batch jobs write only shards and nothing is compacted until the end,
    so a requeued job (post-timeout) and the dependency gate must see progress
    that lives only in shards.
    """
    done: dict[DatasetKey, set[tuple[str, str]]] = defaultdict(set)
    _add_ok_runs(_iter_ok_rows(experiment_folder), done)
    return dict(done)


def sort_topologically(
    enabled: Sequence[InferenceMethod],
    method_to_dependencies: Mapping[InferenceMethod, Sequence[InferenceMethod]],
) -> list[InferenceMethod]:
    """Order the enabled methods so each runs after its dependencies.

    `method_to_dependencies[x] == [a, b]` means **x depends on a and b**: a and b
    run before x.
    Dependencies not in `enabled` (run in a separate invocation) are ignored; the
    run-time gate handles them. Kahn's algorithm, O(V + E); stable by `enabled`
    order; raises on a cycle.
    """
    in_run = set(enabled)
    indegree = {m: 0 for m in enabled}
    dependents: dict[InferenceMethod, list[InferenceMethod]] = {m: [] for m in enabled}
    for m in enabled:
        for dep in method_to_dependencies.get(m, []):
            if dep in in_run:
                indegree[m] += 1
                dependents[dep].append(m)

    queue = deque(m for m in enabled if indegree[m] == 0)
    order: list[InferenceMethod] = []
    while queue:
        m = queue.popleft()
        order.append(m)
        for dependent in dependents[m]:
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                queue.append(dependent)

    if len(order) != len(enabled):
        raise ValueError("dependency cycle among inference methods")
    return order
