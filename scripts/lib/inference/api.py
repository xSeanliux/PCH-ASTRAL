"""Object-returning inference API — the only subprocess site."""

import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import shortuuid
from pydantic import BaseModel

from scripts.lib.inference import method_config, registry
from scripts.lib.model.methods import RunStatus
from scripts.lib.inference.inference import InferenceResult
from scripts.lib.inference.runners import Runner


def infer(
    input_csv: Path, output_dir: Path, runner: Runner[BaseModel]
) -> InferenceResult:
    """Run one unit of work on one dataset.

    OK iff the command exits 0 and writes the point estimate, else the group
    estimate (a method with only a family, like CAMUS, has no point estimate).
    """
    name = runner.get_run_name(input_csv.stem)
    runid = shortuuid.uuid()

    log = runner.get_log_path(output_dir, name)
    log.parent.mkdir(parents=True, exist_ok=True)

    argv = runner.build_argv(runid, input_csv, name, output_dir)

    start = time.monotonic()
    with log.open("w") as log_file:
        proc = subprocess.run(
            argv, check=False, stdout=log_file, stderr=subprocess.STDOUT
        )
    elapsed = time.monotonic() - start

    point_estimate_path = runner.get_point_estimate_path(output_dir, name)
    group_estimate_path = runner.get_group_estimate_path(output_dir, name)
    required_path = point_estimate_path or group_estimate_path
    assert required_path is not None, f"{runner.method} declares no estimate"
    is_ok = proc.returncode == 0 and required_path.exists()
    newick = (
        point_estimate_path.read_text().strip() if is_ok and point_estimate_path else ""
    )
    # Recorded only when the file exists (None = "no set").
    is_group_recorded = (
        is_ok and group_estimate_path is not None and group_estimate_path.exists()
    )

    # dataset_id = the canonical input path (identity); `name` only names on-disk files.
    return InferenceResult(
        dataset_id=registry.canonical_path(input_csv),
        method=runner.method,
        config_hash=method_config.hash_config(runner.config),
        method_config_json=runner.config.model_dump_json(),
        point_estimate_newick=newick,
        runtime_seconds=elapsed,
        status=RunStatus.OK if is_ok else RunStatus.FAILED,
        ran_at=datetime.now(timezone.utc).isoformat(),
        group_estimate_path=str(group_estimate_path) if is_group_recorded else None,
        consensus_method=runner.get_consensus_method(),
        log_path=str(log),
    )
