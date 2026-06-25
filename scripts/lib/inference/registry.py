"""Artifact-model mechanics: run_key, atomic .parts writes, compact, manifest.

The riskiest module — concurrency-safe idempotent registry writes.
"""

import json
import os
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from uuid import uuid4

import polars as pl

from scripts.lib.inference.inference import InferenceResult
from scripts.py.cli.schemata import INFERENCE_REGISTRY_SCHEMA

# Row columns forming the natural run identity (sim keys + method + config_hash).
_KEY_COLUMNS = [
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


def _run_key_from_row(row: dict[str, object]) -> str:
    """Deterministic, filesystem-safe key from a registry row.

    Sim keys are None for atomic runs → fall back to dataset_id.
    """
    sim_keys = [row[c] for c in _KEY_COLUMNS]
    identity = (
        sim_keys if any(k is not None for k in sim_keys[:7]) else [row["dataset_id"]]
    )
    identity = identity + [row["method"], row["config_hash"]]
    canonical = "\x00".join("" if v is None else str(v) for v in identity)
    return sha1(canonical.encode("utf-8")).hexdigest()


def run_key(result: InferenceResult) -> str:
    return _run_key_from_row(result.to_registry_row())


def write_part(result: InferenceResult, parts_dir: Path) -> Path:
    """Atomically stage one run's row at parts_dir/{run_key}.json.

    Write a per-process temp file, then os.replace onto the target so concurrent
    duplicate runs never tear it — last writer wins.
    """
    parts_dir.mkdir(parents=True, exist_ok=True)
    key = run_key(result)
    final = parts_dir / f"{key}.json"
    tmp = parts_dir / f"{key}.{os.getpid()}.{uuid4().hex}.tmp"
    tmp.write_text(json.dumps(result.to_registry_row()))
    os.replace(tmp, final)
    return final


def compact(experiment_folder: Path) -> Path:
    """Merge inference_data/.parts/*.json → inference_registry.csv.

    Dedup by run_key keeping newest ran_at (last-writer-wins). Idempotent.
    """
    inference_dir = experiment_folder / "inference_data"
    parts_dir = inference_dir / ".parts"
    out = inference_dir / "inference_registry.csv"

    by_key: dict[str, dict[str, object]] = {}
    for part in sorted(parts_dir.glob("*.json")):
        row = json.loads(part.read_text())
        key = _run_key_from_row(row)
        prev = by_key.get(key)
        # ran_at is an ISO timestamp string → lexical compare matches chronological.
        if prev is None or str(row["ran_at"]) >= str(prev["ran_at"]):
            by_key[key] = row

    inference_dir.mkdir(parents=True, exist_ok=True)
    df = pl.DataFrame(list(by_key.values()), schema=INFERENCE_REGISTRY_SCHEMA)
    df.write_csv(out)
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
