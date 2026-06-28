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
    runner = RUNNERS[method]

    argv = runner.build_argv(runid, input_csv, name, output_dir)
    log = runner.log_path(output_dir, name)
    log.parent.mkdir(parents=True, exist_ok=True)

    start = time.monotonic()
    with log.open("w") as log_file:
        proc = subprocess.run(
            argv, check=False, stdout=log_file, stderr=subprocess.STDOUT
        )
    elapsed = time.monotonic() - start
    status = RunStatus.OK if proc.returncode == 0 else RunStatus.FAILED

    point_estimate = runner.point_estimate_path(output_dir, name)
    newick = (
        point_estimate.read_text().strip()
        if status is RunStatus.OK and point_estimate.exists()
        else ""
    )

    return InferenceResult(
        dataset_id=name,
        tree_inference_method=method,
        config_hash=method_config.config_hash(config),
        method_config_json=config.model_dump_json(),
        point_estimate_newick=newick,
        runtime_seconds=elapsed,
        status=status,
        ran_at=datetime.now(timezone.utc).isoformat(),
        tree_set_path=str(runner.group_estimate_path(output_dir, name)),
        consensus_method=runner.consensus_method(),
        log_path=str(log),
    )
