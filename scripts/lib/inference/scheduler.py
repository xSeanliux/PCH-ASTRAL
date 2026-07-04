"""Dependency-aware scheduling for the inference pipeline.

The registry holds only successful results, so a `(dataset, method, config_hash)`
row means that unit is done. `completed_runs` loads those into a lookup that
drives both **resume** (skip an exact already-done unit) and the **dependency
gate** (a method's output is available). Blocks/failures are logged by the
caller, never recorded. See docs/ARCHITECTURE.md.
"""

from collections import defaultdict, deque
from collections.abc import Mapping
from pathlib import Path

import polars as pl

from scripts.lib.inference import registry
from scripts.lib.inference.inference import RunStatus, TreeInferenceMethod
from scripts.py.cli.schemata import INFERENCE_REGISTRY_SCHEMA

# A registry/sim cell value, and a dataset's identity (its join-key values).
Cell = str | int | float | None
DatasetKey = tuple[Cell, ...]


def dataset_key(row: Mapping[str, Cell]) -> DatasetKey:
    """A dataset's identity — its join-key values, in DATASET_KEY_COLUMNS order."""
    return tuple(row[c] for c in registry.DATASET_KEY_COLUMNS)


def completed_runs(experiment_folder: Path) -> dict[DatasetKey, set[tuple[str, str]]]:
    """`{dataset → {(method, config_hash)}}` for successful prior runs.

    `(method, config_hash)` present ⇒ that exact unit is done (resume skip);
    the method present (any config) ⇒ its output is available (dependency gate).
    """
    out = registry.registry_path(experiment_folder)
    if not out.exists():
        return {}
    done: dict[DatasetKey, set[tuple[str, str]]] = defaultdict(set)
    for row in pl.read_csv(out, schema=INFERENCE_REGISTRY_SCHEMA).iter_rows(named=True):
        if row["status"] != RunStatus.OK.value:  # trust only successes
            continue
        done[dataset_key(row)].add((row["method"], row["config_hash"]))
    return dict(done)


def topological_order(
    enabled: list[TreeInferenceMethod],
    deps_of: Mapping[TreeInferenceMethod, list[TreeInferenceMethod]],
) -> list[TreeInferenceMethod]:
    """Order the enabled methods so each runs after its dependencies.

    `deps_of[x] == [a, b]` means **x depends on a and b** — a and b run before x.
    Dependencies not in `enabled` (run in a separate invocation) are ignored; the
    run-time gate handles them. Kahn's algorithm, O(V + E); stable by `enabled`
    order; raises on a cycle.
    """
    in_run = set(enabled)
    indegree = {m: 0 for m in enabled}
    dependents: dict[TreeInferenceMethod, list[TreeInferenceMethod]] = {
        m: [] for m in enabled
    }
    for m in enabled:
        for dep in deps_of.get(m, []):
            if dep in in_run:
                indegree[m] += 1
                dependents[dep].append(m)

    queue = deque(m for m in enabled if indegree[m] == 0)
    order: list[TreeInferenceMethod] = []
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
