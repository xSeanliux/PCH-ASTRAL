"""The network family registry: one row per (dataset, guide tree, k).

CAMUS writes each run's family as a CSV. `write_family` reads it, prepends the
run's identity, and appends JSON lines to this job's shard; `compact` merges
the shards into camus_registry.csv. Same shard/compact shape as `registry`.
"""

import json
from collections.abc import Mapping
from pathlib import Path

import polars as pl

from scripts.lib.inference import registry
from scripts.lib.inference.inference import InferenceResult
from scripts.lib.inference.registry import Cell
from scripts.py.cli.schemata import CAMUS_REGISTRY_SCHEMA

# CAMUS's own header, in order. Anything else is a CAMUS we do not know.
CAMUS_COLUMNS = ["Number of Branches", "Quartet Satisfied Percent", "Extended Newick"]
_RENAME = dict(zip(CAMUS_COLUMNS, ["k", "qsat_percent", "network_newick"]))
_KEY_COLUMNS = ["dataset_id", "config_hash", "k"]


def shards_dir(experiment_folder: Path) -> Path:
    return experiment_folder / "inference_data" / "camus_shards"


def registry_path(experiment_folder: Path) -> Path:
    return experiment_folder / "inference_data" / "camus_registry.csv"


def _family_key(row: Mapping[str, Cell]) -> str:
    return "|".join(str(row.get(c)) for c in _KEY_COLUMNS)


def write_family(
    result: InferenceResult, guide_tree: str, experiment_folder: Path
) -> Path:
    """Append the run's family, one JSON line per k, to this job's shard.

    Raises ValueError when the family is missing, empty, torn, or its header
    is not CAMUS's, so the caller can count the run as failed and let the next
    run retry."""
    if result.tree_set_path is None or not Path(result.tree_set_path).is_file():
        raise ValueError(f"no network family at {result.tree_set_path}")
    try:
        family = pl.read_csv(result.tree_set_path)
    except pl.exceptions.PolarsError as e:
        raise ValueError(f"unreadable family at {result.tree_set_path}: {e}") from e
    if family.columns != CAMUS_COLUMNS:
        raise ValueError(
            f"unexpected family header {family.columns}; want {CAMUS_COLUMNS}"
        )
    if family.height == 0:
        raise ValueError(f"no rows in family at {result.tree_set_path}")
    if family.null_count().row(0, named=True) != dict.fromkeys(CAMUS_COLUMNS, 0):
        raise ValueError(f"null cell(s) (torn write?) in {result.tree_set_path}")
    first_k = family[CAMUS_COLUMNS[0]][0]
    if first_k != 0:
        raise ValueError(f"first k is {first_k}, not 0, in {result.tree_set_path}")
    identity = {
        "dataset_id": result.dataset_id,
        "guide_tree": guide_tree,
        "config_hash": result.config_hash,
        "runtime_seconds": result.runtime_seconds,
        "status": result.status.value,
        "ran_at": result.ran_at,
        "log_path": result.log_path,
    }
    shards = shards_dir(experiment_folder)
    shards.mkdir(parents=True, exist_ok=True)
    shard = shards / f"{registry.current_shard_id()}.jsonl"
    with shard.open("a") as f:
        for row in family.rename(_RENAME).iter_rows(named=True):
            f.write(json.dumps({**identity, **row}) + "\n")
    return shard


def compact(experiment_folder: Path, *, cleanup: bool = True) -> Path:
    """Merge camus_shards/*.jsonl -> camus_registry.csv, one row per
    (dataset, config, k), the newest ran_at winning.

    Dedup is per k (merge_shards' key), not per family: a rerun with the same
    (dataset, config) that writes a SHORTER family would otherwise leave the
    earlier run's higher-k rows beside the new ones. So after merging, drop
    every row whose ran_at isn't the newest within its (dataset, config).
    """
    out = registry.merge_shards(
        shards_dir(experiment_folder),
        registry_path(experiment_folder),
        CAMUS_REGISTRY_SCHEMA,
        _family_key,
        cleanup=cleanup,
    )
    df = pl.read_csv(out, schema=CAMUS_REGISTRY_SCHEMA)
    if df.height:
        newest = df.group_by(_KEY_COLUMNS[:-1]).agg(pl.col("ran_at").max())
        df = df.join(newest, on=_KEY_COLUMNS[:-1], suffix="_newest").filter(
            pl.col("ran_at") == pl.col("ran_at_newest")
        )
        df.drop("ran_at_newest").write_csv(out)
    return out


def compact_if_any(experiment_folder: Path) -> Path | None:
    """Compact when this experiment has ever run CAMUS; else leave no file behind."""
    if (
        shards_dir(experiment_folder).exists()
        or registry_path(experiment_folder).exists()
    ):
        return compact(experiment_folder)
    return None
