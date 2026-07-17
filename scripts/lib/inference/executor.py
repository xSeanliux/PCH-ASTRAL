"""SLURM fan-out for `pch experiment inference` via submitit.

One submitit job per (condition, method): condition = the dataset's parent-dir
name (matches run_parallel_sim.sh). Batch jobs write only shards (`no_compact`);
a final compact job (`afterany` on all of them) merges + writes the manifest.
Method deps become `afterok` edges within a condition (MP4/GA -> ASTRAL3). The
4 h `secondary` cap is absorbed by submitit requeue-on-timeout
(`slurm_max_num_timeout`), so `completed_runs` idempotency makes reruns safe.

`run_batch`/`run_compact` are module-level so submitit can pickle them; they take
paths/str only and reload the config from a spec snapshot the executor writes.
See specs/cli_specs/slurm_fanout_spec.md section C.
"""

import os
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import polars as pl
import yaml
from rich import print
from submitit import AutoExecutor, Job

from scripts.lib.experiment import ExperimentConfig
from scripts.lib.inference import registry
from scripts.lib.inference.inference import TreeInferenceMethod
from scripts.lib.inference.method_config import config_for
from scripts.lib.inference.runners import RUNNERS
from scripts.py.cli.handle_inference import handle_inference, select_methods
from scripts.py.cli.schemata import INFERENCE_REGISTRY_SCHEMA

# One sim-registry row (polars iter_rows(named=True)); we only read "path".
Row = Mapping[str, str | int | float | None]
# submitit param values across the jobs we build.
Param = str | int | list[str] | dict[str, str]

# 2 resource tiers, not a per-method map (spec §C). Seed from the legacy sbatch,
# tune later. ASTRAL3 is heavy (big heap); MP4/GA are light.
_HEAVY_MEM_GB = 64
_LIGHT_MEM_GB = 8
_HEAVY_CPUS = 8
_LIGHT_CPUS = 2
_PARTITION = "secondary"
_TIMEOUT_MIN = 240  # the secondary-queue 4 h cap; requeue-on-timeout handles reruns

Tier = Literal["heavy", "light"]
Kind = Literal["batch", "compact"]
DepMode = Literal["afterok", "afterany"]


@dataclass(frozen=True)
class JobSpec:
    """One planned submitit job. `kind="compact"` leaves method/datasets_file/tier
    empty and depends `afterany` on every batch job's label."""

    label: str  # unique job id in the plan; deps reference it
    kind: Kind
    mem_gb: int
    cpus: int
    dep_labels: tuple[str, ...]
    dep_mode: DepMode
    condition: str | None = None
    method: str | None = None  # TreeInferenceMethod value
    datasets_file: Path | None = None
    tier: Tier | None = None


def _load_config(spec_path: Path) -> ExperimentConfig:
    return ExperimentConfig.model_validate(yaml.safe_load(spec_path.read_text()))


def run_batch(spec_path: str, datasets_file: str, method: str) -> None:
    """submitit job body: run one method over one condition's datasets, shards only."""
    config = _load_config(Path(spec_path))
    handle_inference(
        config, datasets=Path(datasets_file), method=method, no_compact=True
    )


def run_compact(spec_path: str) -> None:
    """submitit job body: merge shards + write the manifest (the run that owns it)."""
    config = _load_config(Path(spec_path))
    folder = config.experiment_folder
    methods = [m.value for m in select_methods(config.methods)]
    registry.init_manifest(folder, methods)
    out = registry.compact(folder)
    ok = (
        pl.read_csv(out, schema=INFERENCE_REGISTRY_SCHEMA).height if out.exists() else 0
    )
    # The fan-out compact can't see per-run failures: batch jobs logged their own
    # skipped/blocked/failed and exit independently. Record only the cumulative ok
    # count (all-time registry rows, inflated on incremental reruns) — do NOT stamp
    # a fabricated 0-failure tally that reads as a clean run. Use `pch experiment
    # status` to find gaps.
    registry.finalize_manifest(folder, {"ok_cumulative": ok})


class SlurmExecutor:
    def __init__(self, config: ExperimentConfig) -> None:
        self.config = config
        self._inference_dir = config.experiment_folder / "inference_data"

    def _batches_dir(self) -> Path:
        return self._inference_dir / "batches"

    def _label(self, condition: str, method: str) -> str:
        return f"{method}@{condition}"

    def _group_conditions(self, rows: Iterable[Row]) -> dict[str, list[Path]]:
        """condition (parent-dir name) -> its dataset paths, insertion-ordered.
        Errors if two distinct parent dirs share a name (they'd merge into one
        batch/label and silently drop datasets)."""
        conditions: dict[str, list[Path]] = {}
        seen_parents: dict[str, Path] = {}
        for row in rows:
            p = Path(str(row["path"]))
            name = p.parent.name
            prev = seen_parents.setdefault(name, p.parent)
            if prev != p.parent:
                raise ValueError(
                    f"condition name {name!r} collides across distinct dirs: "
                    f"{prev} vs {p.parent}. Rename one to keep batches distinct."
                )
            conditions.setdefault(name, []).append(p)
        return conditions

    def _plan(
        self,
        conditions: Mapping[str, list[Path]],
        *,
        method: str | None = None,
        astral_mem_gb: int | None,
    ) -> list[JobSpec]:
        """Pure planner (no submitit): ordered JobSpecs, one per (condition, method)
        in topological method order, then a final compact job on all of them.
        `method` restricts to that single enabled method (deps ran in a prior run)."""
        methods = select_methods(self.config.methods)  # topo order: deps first
        if method is not None:
            methods = [m for m in methods if method in (m.value, m.name)]
            if not methods:
                raise ValueError(
                    f"Method {method!r} is not enabled in the config; "
                    "cannot restrict the fan-out to it."
                )
        enabled = {m.value for m in methods}
        specs: list[JobSpec] = []
        method_labels: list[str] = []

        for condition in conditions:
            for m in methods:
                cfg = config_for(self.config.methods, m)
                assert cfg is not None  # select_methods only yields enabled methods
                # deps present in this run become same-condition afterok edges
                dep_labels = tuple(
                    self._label(condition, d.value)
                    for d in RUNNERS[m].dependencies(cfg)
                    if d.value in enabled
                )
                heavy = m is TreeInferenceMethod.PCH_ASTRAL3
                label = self._label(condition, m.value)
                # `is None`, not `or`: `--astral-mem-gb 0` is an explicit override,
                # not a request for the 64g default.
                heavy_mem = _HEAVY_MEM_GB if astral_mem_gb is None else astral_mem_gb
                specs.append(
                    JobSpec(
                        label=label,
                        kind="batch",
                        mem_gb=heavy_mem if heavy else _LIGHT_MEM_GB,
                        cpus=_HEAVY_CPUS if heavy else _LIGHT_CPUS,
                        dep_labels=dep_labels,
                        dep_mode="afterok",
                        condition=condition,
                        method=m.value,
                        datasets_file=self._batches_dir() / f"{condition}.txt",
                        tier="heavy" if heavy else "light",
                    )
                )
                method_labels.append(label)

        specs.append(
            JobSpec(
                label="compact",
                kind="compact",
                mem_gb=_LIGHT_MEM_GB,
                cpus=_LIGHT_CPUS,
                dep_labels=tuple(method_labels),
                dep_mode="afterany",  # compact runs even if some methods failed
            )
        )
        return specs

    def _write_batches(self, conditions: Mapping[str, list[Path]]) -> None:
        self._batches_dir().mkdir(parents=True, exist_ok=True)
        for condition, paths in conditions.items():
            (self._batches_dir() / f"{condition}.txt").write_text(
                "".join(f"{p}\n" for p in paths)
            )

    def _spec_snapshot(self) -> Path:
        """Serialize the config to a picklable/importable spec path for the jobs.
        Sidesteps needing the original yaml location; jobs reload from this.

        Unique name per submission: jobs reload it lazily at run time (incl. a
        requeue hours later), so a fixed path would let a later `--executor slurm`
        wave (edited yaml) overwrite the config a still-queued wave reads. A
        per-submission name isolates each wave.
        """
        p = self._inference_dir / f"spec.snapshot.{uuid.uuid4().hex[:12]}.yaml"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(yaml.safe_dump(self.config.model_dump(mode="json")))
        return p

    def fan_out(
        self,
        rows: Iterable[Row],
        *,
        method: str | None = None,
        datasets: Path | None = None,
        resubmits: int = 3,
        astral_mem_gb: int | None = None,
        dry_run: bool = False,
    ) -> list[JobSpec] | list[Job[None]]:
        """Filter rows (`datasets` paths file), write per-condition batch files,
        plan the DAG (`method` restricts to one enabled method), then print it
        (dry_run) or submit it. Returns the plan (dry_run) or the submitit Jobs."""
        rows = list(rows)
        if datasets is not None:
            wanted = {
                registry.canonical_path(line.strip())
                for line in datasets.read_text().splitlines()
                if line.strip()
            }
            rows = [
                r for r in rows if registry.canonical_path(str(r["path"])) in wanted
            ]

        conditions = self._group_conditions(rows)  # group once, reuse
        self._write_batches(conditions)
        plan = self._plan(conditions, method=method, astral_mem_gb=astral_mem_gb)

        if dry_run:
            for spec in plan:
                deps = (
                    f" {spec.dep_mode}:{','.join(spec.dep_labels)}"
                    if spec.dep_labels
                    else ""
                )
                print(
                    f"[cyan]{spec.label}[/cyan] {spec.kind} "
                    f"tier={spec.tier or '-'} mem={spec.mem_gb}g cpus={spec.cpus}{deps}"
                )
            return list(plan)

        return self._submit(plan, resubmits)

    def _submit(self, plan: list[JobSpec], resubmits: int) -> list[Job[None]]:
        # Absolute so the config file resolves regardless of the compute node's cwd
        # (safe: it's an output/config path, not a dataset_id). Dataset paths inside
        # the batch files stay relative and resolve against `chdir` below.
        spec_path = os.path.abspath(str(self._spec_snapshot()))
        # submitit doesn't pin the job cwd; pin it to the submission dir so every
        # repo-root-relative path (batch files, dataset paths) resolves on the node
        # exactly as it does locally — without rewriting (and breaking) dataset_id.
        chdir = os.getcwd()
        submitit_dir = self._inference_dir / "submitit"
        # Pin cluster="slurm": AutoExecutor auto-detects from `srun` (not `sbatch`),
        # so if the two diverge it would silently pick LocalExecutor, which ignores
        # slurm_additional_parameters — dropping the afterok dep edges and racing
        # ASTRAL3 ahead of MP4/GA. Pinning raises "no srun" instead of degrading.
        # max_num_timeout is a constructor arg (forwarded to SlurmExecutor as
        # max_num_timeout), NOT an update_parameters key. Requeue-on-timeout count.
        ex = AutoExecutor(
            folder=submitit_dir, cluster="slurm", slurm_max_num_timeout=resubmits
        )
        jobs: dict[str, Job[None]] = {}
        submitted: list[Job[None]] = []

        for spec in plan:  # topo order ⇒ every dep already submitted
            # Xmx at ~85% of the cgroup: leaves headroom for JVM overhead/off-heap so
            # SLURM doesn't OOM-kill. ponytail: lower the 0.85 further if still OOM.
            xmx_gb = max(1, int(spec.mem_gb * 0.85))
            extra: dict[str, str] = {"chdir": chdir}
            if spec.dep_labels:
                dep_ids = ":".join(jobs[label].job_id for label in spec.dep_labels)
                extra["dependency"] = f"{spec.dep_mode}:{dep_ids}"
            params: dict[str, Param] = {
                "slurm_partition": _PARTITION,
                "timeout_min": _TIMEOUT_MIN,
                "cpus_per_task": spec.cpus,
                "mem_gb": spec.mem_gb,
                # Node-local scratch dodges the 99-char MrBayes path cap.
                "slurm_setup": [
                    "export PCH_SCRATCH=/tmp/pch.$SLURM_JOB_ID",
                    f"export PCH_ASTRAL_XMX={xmx_gb}g",
                ],
                "slurm_additional_parameters": extra,
            }
            ex.update_parameters(**params)

            if spec.kind == "compact":
                job = ex.submit(run_compact, spec_path)
            else:
                assert spec.datasets_file is not None and spec.method is not None
                job = ex.submit(
                    run_batch, spec_path, str(spec.datasets_file), spec.method
                )
            jobs[spec.label] = job
            submitted.append(job)
        return submitted
