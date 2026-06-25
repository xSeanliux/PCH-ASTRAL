"""Object-returning inference API — the only subprocess site."""

import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import shortuuid
from pydantic import BaseModel

from scripts.lib.inference import method_config, runners
from scripts.lib.inference.inference import InferenceResult, TreeInferenceMethod


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

    argv = runners.build_argv(method, runid, input_csv, name, output_dir, config)
    missing = runners.missing_prerequisites(method, config, output_dir, name)
    if missing:
        joined = ", ".join(str(p) for p in missing)
        raise FileNotFoundError(
            f"{method} needs MP4/GA outputs first; missing: {joined}"
        )
    log = runners.log_path(method, output_dir, name)
    log.parent.mkdir(parents=True, exist_ok=True)

    start = time.monotonic()
    with log.open("w") as log_file:
        proc = subprocess.run(
            argv, check=False, stdout=log_file, stderr=subprocess.STDOUT
        )
    elapsed = time.monotonic() - start
    status = "ok" if proc.returncode == 0 else "failed"

    point_estimate = runners.point_estimate_path(method, output_dir, name)
    newick = (
        point_estimate.read_text().strip()
        if status == "ok" and point_estimate.exists()
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
        tree_set_path=str(runners.group_estimate_path(method, output_dir, name)),
        consensus_method=runners.consensus_method(method),
        log_path=str(log),
    )
