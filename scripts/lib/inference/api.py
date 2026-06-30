"""Object-returning inference API — the only subprocess site."""

import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import shortuuid
from pydantic import BaseModel

from scripts.lib.inference import method_config
from scripts.lib.inference.inference import (
    InferenceResult,
    RunStatus,
    TreeInferenceMethod,
)
from scripts.lib.inference.runners import RUNNERS


def failed_result(
    name: str,
    output_dir: Path,
    method: TreeInferenceMethod,
    config: BaseModel,
    reason: str,
) -> InferenceResult:
    """A FAILED result with full fields + a written log. Single source of truth so
    every skip path produces identical, dedupe-safe rows (run_key includes config_hash)."""
    runner = RUNNERS.get(method)
    if runner is None:
        raise ValueError(f"No runner registered for method {method.value!r}")
    log = runner.log_path(output_dir, name)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(reason)
    return InferenceResult(
        dataset_id=name,
        tree_inference_method=method,
        config_hash=method_config.config_hash(config),
        method_config_json=config.model_dump_json(),
        point_estimate_newick="",
        runtime_seconds=0.0,
        status=RunStatus.FAILED,
        ran_at=datetime.now(timezone.utc).isoformat(),
        tree_set_path=None,
        consensus_method=runner.consensus_method(),
        log_path=str(log),
    )


def infer(
    input_csv: Path,
    output_dir: Path,
    method: TreeInferenceMethod,
    config: BaseModel,
    *,
    name: str | None = None,
) -> InferenceResult:
    name = name or input_csv.stem
    runid = shortuuid.uuid()
    runner = RUNNERS.get(method)
    if runner is None:
        raise ValueError(f"No runner registered for method {method.value!r}")

    log = runner.log_path(output_dir, name)
    log.parent.mkdir(parents=True, exist_ok=True)

    # Missing prereqs => FAILED result (never raise: infer always returns one).
    missing = runner.missing_prerequisites(config, output_dir, name)
    if missing:
        joined = ", ".join(str(p) for p in missing)
        return failed_result(
            name,
            output_dir,
            method,
            config,
            f"{method} needs MP4/GA outputs first; missing: {joined}",
        )

    argv = runner.build_argv(runid, input_csv, name, output_dir, config)

    start = time.monotonic()
    with log.open("w") as log_file:
        proc = subprocess.run(
            argv, check=False, stdout=log_file, stderr=subprocess.STDOUT
        )
    elapsed = time.monotonic() - start

    # A run is OK only if it exited 0 AND actually produced its point estimate.
    point_estimate = runner.point_estimate_path(output_dir, name)
    ok = proc.returncode == 0 and point_estimate.exists()
    status = RunStatus.OK if ok else RunStatus.FAILED
    newick = point_estimate.read_text().strip() if ok else ""

    # tree_set_path only when the file actually exists (None signals "no set").
    group = runner.group_estimate_path(output_dir, name)
    tree_set_path = str(group) if ok and group is not None and group.exists() else None

    return InferenceResult(
        dataset_id=name,
        tree_inference_method=method,
        config_hash=method_config.config_hash(config),
        method_config_json=config.model_dump_json(),
        point_estimate_newick=newick,
        runtime_seconds=elapsed,
        status=status,
        ran_at=datetime.now(timezone.utc).isoformat(),
        tree_set_path=tree_set_path,
        consensus_method=runner.consensus_method(),
        log_path=str(log),
    )
