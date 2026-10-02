"""Object-returning inference API — the only subprocess site."""

import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import shortuuid
from pydantic import BaseModel

from scripts.lib.inference import method_config, registry
from scripts.lib.inference.inference import (
    ConsensusMethod,
    InferenceMethod,
    InferenceResult,
    NetworkInferenceMethod,
    RunStatus,
    TreeInferenceMethod,
)
from scripts.lib.inference.runners import NETWORK_RUNNERS, RUNNERS, TREE_RUNNERS


def infer(
    input_csv: Path,
    output_dir: Path,
    method: InferenceMethod,
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

    argv = runner.build_argv(runid, input_csv, name, output_dir, config)

    start = time.monotonic()
    with log.open("w") as log_file:
        proc = subprocess.run(
            argv, check=False, stdout=log_file, stderr=subprocess.STDOUT
        )
    elapsed = time.monotonic() - start

    # A run is OK only if it exited 0 AND actually produced its estimate.
    newick = ""
    tree_set_path: str | None = None
    consensus: ConsensusMethod | None = None
    if isinstance(method, NetworkInferenceMethod):
        # A network family has no single estimate: choosing a k is analysis. The
        # registry row carries the family's path and leaves the newick empty.
        family = NETWORK_RUNNERS[method].family_path(output_dir, name)
        ok = proc.returncode == 0 and family.exists()
        tree_set_path = str(family) if ok else None
    else:
        assert isinstance(method, TreeInferenceMethod)
        tree_runner = TREE_RUNNERS[method]
        point_estimate = tree_runner.point_estimate_path(output_dir, name)
        ok = proc.returncode == 0 and point_estimate.exists()
        newick = point_estimate.read_text().strip() if ok else ""
        # tree_set_path only when the file actually exists (None signals "no set").
        group = tree_runner.group_estimate_path(output_dir, name)
        if ok and group is not None and group.exists():
            tree_set_path = str(group)
        consensus = tree_runner.consensus_method()
    status = RunStatus.OK if ok else RunStatus.FAILED

    # dataset_id = the canonical input path (identity); `name` (stem) only names
    # on-disk files.
    return InferenceResult(
        dataset_id=registry.canonical_path(input_csv),
        tree_inference_method=method,
        config_hash=method_config.config_hash(config),
        method_config_json=config.model_dump_json(),
        point_estimate_newick=newick,
        runtime_seconds=elapsed,
        status=status,
        ran_at=datetime.now(timezone.utc).isoformat(),
        tree_set_path=tree_set_path,
        consensus_method=consensus,
        log_path=str(log),
    )
