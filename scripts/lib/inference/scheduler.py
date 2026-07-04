"""Dependency-aware scheduling for the inference pipeline.

The registry holds ONLY successful results, so a row for `(dataset, method)`
means that method produced usable output for that dataset. The scheduler builds
on that ledger:

- **skip** a method whose exact `(dataset, method, config_hash)` is already
  recorded (resume — don't redo work);
- **block** a method whose dependency has no successful result yet — counting
  both prior runs (the registry) and methods that already succeeded this run;
- otherwise **run** it.

Failures and blocks are NOT written to the registry — they're logged by the
caller. This module is pure/stateful-in-memory; it does no I/O beyond reading
the registry once when the `Ledger` is built.
"""

from collections import defaultdict
from pathlib import Path

from scripts.lib.inference import registry
from scripts.lib.inference.inference import TreeInferenceMethod

# A dataset's identity = the dedup run_key minus (method, config_hash).
_DATASET_COLUMNS = registry._KEY_COLUMNS[:-2]


def dataset_key(row: dict[str, object]) -> tuple:
    """Identity of a dataset from a registry/sim row (its join keys)."""
    return tuple(row.get(c) for c in _DATASET_COLUMNS)


def topological_order(
    enabled: list[TreeInferenceMethod],
    deps_of: dict[TreeInferenceMethod, list[TreeInferenceMethod]],
) -> list[TreeInferenceMethod]:
    """Order the enabled methods so each follows the enabled deps it needs.

    Dependencies not in `enabled` (e.g. run in a separate invocation) are ignored
    here — the run-time gate handles them. Stable by input order; raises on a cycle.
    """
    in_run = set(enabled)
    result: list[TreeInferenceMethod] = []
    done: set[TreeInferenceMethod] = set()
    pending = list(enabled)
    while pending:
        ready = [
            m for m in pending if all(d in done for d in deps_of[m] if d in in_run)
        ]
        if not ready:
            raise ValueError("dependency cycle among inference methods")
        for m in ready:
            result.append(m)
            done.add(m)
            pending.remove(m)
    return result


class Ledger:
    """Which `(dataset, method)` pairs have succeeded — seeded from the registry
    (prior runs), updated as methods succeed this run."""

    def __init__(self, experiment_folder: Path) -> None:
        self._done_keys: set[str] = set()  # full run_key → resume (exact config)
        self._ok: dict[tuple, set[str]] = defaultdict(set)  # dataset → {method.value}
        for row in registry.load_rows(experiment_folder):
            self._done_keys.add(registry.run_key(row))
            self._ok[dataset_key(row)].add(str(row["method"]))

    def already_done(
        self, keys: dict[str, object], method: TreeInferenceMethod, config_hash: str
    ) -> bool:
        """Same dataset + method + config already succeeded (resume → skip)."""
        probe = {**keys, "method": method.value, "config_hash": config_hash}
        return registry.run_key(probe) in self._done_keys

    def unmet_dependencies(
        self, dkey: tuple, deps: list[TreeInferenceMethod]
    ) -> list[TreeInferenceMethod]:
        """Deps with no successful result for this dataset (this run or prior)."""
        ok = self._ok[dkey]
        return [d for d in deps if d.value not in ok]

    def mark_ok(self, dkey: tuple, method: TreeInferenceMethod) -> None:
        self._ok[dkey].add(method.value)
