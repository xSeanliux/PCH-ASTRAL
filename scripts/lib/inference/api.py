"""Object-returning inference API — the only subprocess site."""

import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import shortuuid

from scripts.lib.inference import method_config, registry
from scripts.lib.model.methods import ConsensusMethod, RunStatus
from scripts.lib.inference.inference import (
    InferenceResult,
)
from scripts.lib.inference.runners import NetworkRunner, Runner, TreeRunner


def infer(
    input_csv: Path,
    output_dir: Path,
    runner: Runner,
    *,
    name: str | None = None,
) -> InferenceResult:
    name = name or input_csv.stem
    runid = shortuuid.uuid()

    log = runner.log_path(output_dir, name)
    log.parent.mkdir(parents=True, exist_ok=True)

    argv = runner.build_argv(runid, input_csv, name, output_dir)

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
    if isinstance(runner, NetworkRunner):
        # A network family has no single estimate: choosing a k is analysis. The
        # registry row carries the family's path and leaves the newick empty.
        # ponytail: family-as-CSV is CAMUS's shape; SNaQ/PhyloNet get their own branch.
        family_path = runner.family_path(output_dir, name)
        is_ok = proc.returncode == 0 and family_path.exists()
        tree_set_path = str(family_path) if is_ok else None
    else:
        assert isinstance(runner, TreeRunner)
        point_estimate_path = runner.point_estimate_path(output_dir, name)
        is_ok = proc.returncode == 0 and point_estimate_path.exists()
        newick = point_estimate_path.read_text().strip() if is_ok else ""
        # tree_set_path only when the file actually exists (None signals "no set").
        group_estimate_path = runner.group_estimate_path(output_dir, name)
        if is_ok and group_estimate_path is not None and group_estimate_path.exists():
            tree_set_path = str(group_estimate_path)
        consensus = runner.consensus_method()
    status = RunStatus.OK if is_ok else RunStatus.FAILED

    # dataset_id = the canonical input path (identity); `name` (stem) only names
    # on-disk files.
    return InferenceResult(
        dataset_id=registry.canonical_path(input_csv),
        tree_inference_method=runner.method,
        config_hash=method_config.config_hash(runner.config),
        method_config_json=runner.config.model_dump_json(),
        point_estimate_newick=newick,
        runtime_seconds=elapsed,
        status=status,
        ran_at=datetime.now(timezone.utc).isoformat(),
        tree_set_path=tree_set_path,
        consensus_method=consensus,
        log_path=str(log),
    )
