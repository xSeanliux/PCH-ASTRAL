"""Per-job shard registry.

Each SLURM job (or local process) appends its run rows to its own shard file —
one writer per shard, so no lock and no shared-file contention (flock is
unreliable on NFS/Lustre). `compact` merges all shards into the single canonical
inference_registry.csv (last-writer-wins by ran_at) and deletes the shards, so no
junk files linger.
"""

import json
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from scripts.lib.inference.inference import InferenceResult
from scripts.py.cli.schemata import INFERENCE_REGISTRY_SCHEMA

# Human-readable dedup identity (no opaque hash filename). config_hash is the
# only hashed term and is sha256 (see method_config.config_hash).
_KEY_COLUMNS = [
    "dataset_id",
    "poly_level",
    "character_count",
    "min_tree_height",
    "homoplasy_factor",
    "horizontal_edges",
    "model_tree",
    "replica",
    "method",
    "config_hash",
]


def _keyval(v: object) -> str:
    # Stable across read paths: floats via repr so 1.0 doesn't become "1".
    if v is None:
        return ""
    if isinstance(v, float):
        return repr(v)
    return str(v)


def run_key(row: Mapping[str, object]) -> str:
    """Readable dedup key: the join keys + method + config_hash, '|'-joined."""
    return "|".join(_keyval(row.get(c)) for c in _KEY_COLUMNS)


def _ran_at(row: Mapping[str, object]) -> datetime:
    # Parse the ISO8601 timestamp so the tie-break is correct across offsets,
    # not a lexical string compare that assumes everyone emits +00:00.
    return datetime.fromisoformat(str(row["ran_at"]))


def current_shard_id() -> str:
    """One shard per SLURM (array) job; per-process locally. One writer per shard."""
    array_job = os.environ.get("SLURM_ARRAY_JOB_ID")
    if array_job:
        return f"{array_job}_{os.environ.get('SLURM_ARRAY_TASK_ID', '0')}"
    return os.environ.get("SLURM_JOB_ID") or f"local-{os.getpid()}"


def _shards_dir(experiment_folder: Path) -> Path:
    return experiment_folder / "inference_data" / "shards"


def write_result(result: InferenceResult, experiment_folder: Path) -> Path:
    """Append one run's row (JSON line) to this job's shard. Lock-free."""
    shards = _shards_dir(experiment_folder)
    shards.mkdir(parents=True, exist_ok=True)
    shard = shards / f"{current_shard_id()}.jsonl"
    with shard.open("a") as f:
        f.write(json.dumps(result.to_registry_row()) + "\n")
    return shard


def compact(experiment_folder: Path, *, cleanup: bool = True) -> Path:
    """Merge shards/*.jsonl -> inference_registry.csv (last-writer-wins by ran_at).

    Idempotent. With cleanup=True (default) the shard files are removed after a
    successful merge so no staging junk remains.
    """
    inference_dir = experiment_folder / "inference_data"
    shards = _shards_dir(experiment_folder)
    out = inference_dir / "inference_registry.csv"

    by_key: dict[str, dict[str, object]] = {}
    # Seed from the existing registry so incremental compaction (with shard
    # cleanup) accumulates instead of replacing prior rows.
    if out.exists():
        for prev_row in pl.read_csv(out, schema=INFERENCE_REGISTRY_SCHEMA).iter_rows(
            named=True
        ):
            by_key[run_key(prev_row)] = prev_row

    shard_files = sorted(shards.glob("*.jsonl")) if shards.exists() else []
    for sf in shard_files:
        for line in sf.read_text().splitlines():
            if not line.strip():
                continue
            row: dict[str, object] = json.loads(line)
            k = run_key(row)
            prev = by_key.get(k)
            if prev is None or _ran_at(row) >= _ran_at(prev):
                by_key[k] = row

    inference_dir.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(list(by_key.values()), schema=INFERENCE_REGISTRY_SCHEMA).write_csv(out)

    if cleanup:
        for sf in shard_files:
            sf.unlink()
        if shards.exists() and not any(shards.iterdir()):
            shards.rmdir()
    return out


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _manifest_path(experiment_folder: Path) -> Path:
    return experiment_folder / "inference_data" / "manifest.json"


def init_manifest(experiment_folder: Path, methods: list[str]) -> Path:
    path = _manifest_path(experiment_folder)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"created_at": _now(), "completed_at": None, "methods": methods})
    )
    return path


def finalize_manifest(experiment_folder: Path, n_runs: int) -> Path:
    path = _manifest_path(experiment_folder)
    manifest = json.loads(path.read_text()) if path.exists() else {}
    manifest["completed_at"] = _now()
    manifest["n_runs"] = n_runs
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest))
    return path
