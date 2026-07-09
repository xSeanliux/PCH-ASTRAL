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
    # Batch jobs logged their own skipped/blocked/failed; the compact job only sees
    # the merged ok rows, so the manifest tally records that count.
    registry.finalize_manifest(
        folder, {"ok": ok, "skipped": 0, "blocked": 0, "failed": 0}
    )


class SlurmExecutor:
    def __init__(self, config: ExperimentConfig) -> None:
        self.config = config
        self._inference_dir = config.experiment_folder / "inference_data"

    def _batches_dir(self) -> Path:
        return self._inference_dir / "batches"

    def _label(self, condition: str, method: str) -> str:
        return f"{method}@{condition}"

    def _group_conditions(self, rows: Iterable[Row]) -> dict[str, list[Path]]:
        """condition (parent-dir name) -> its dataset paths, insertion-ordered."""
        conditions: dict[str, list[Path]] = {}
        for row in rows:
            p = Path(str(row["path"]))
            conditions.setdefault(p.parent.name, []).append(p)
        return conditions

    def _plan(self, rows: Iterable[Row], *, astral_mem_gb: int | None) -> list[JobSpec]:
        """Pure planner (no submitit): ordered JobSpecs, one per (condition, method)
        in topological method order, then a final compact job on all of them."""
        methods = select_methods(self.config.methods)  # topo order: deps first
        enabled = {m.value for m in methods}
        specs: list[JobSpec] = []
        method_labels: list[str] = []

        for condition in self._group_conditions(rows):
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
                specs.append(
                    JobSpec(
                        label=label,
                        kind="batch",
                        mem_gb=(astral_mem_gb or _HEAVY_MEM_GB)
                        if heavy
                        else _LIGHT_MEM_GB,
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
        Sidesteps needing the original yaml location; jobs reload from this."""
        p = self._inference_dir / "spec.snapshot.yaml"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(yaml.safe_dump(self.config.model_dump(mode="json")))
        return p

    def fan_out(
        self,
        rows: Iterable[Row],
        *,
        resubmits: int = 3,
        astral_mem_gb: int | None = None,
        dry_run: bool = False,
    ) -> list[JobSpec] | list[Job[None]]:
        """Write per-condition batch files, plan the DAG, then either print it
        (dry_run) or submit it. Returns the plan (dry_run) or the submitit Jobs."""
        rows = list(rows)  # consumed twice (batches + plan)
        self._write_batches(self._group_conditions(rows))
        plan = self._plan(rows, astral_mem_gb=astral_mem_gb)

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
        spec_path = str(self._spec_snapshot())
        submitit_dir = self._inference_dir / "submitit"
        jobs: dict[str, Job[None]] = {}
        submitted: list[Job[None]] = []

        for spec in plan:  # topo order ⇒ every dep already submitted
            ex = AutoExecutor(folder=submitit_dir)
            params: dict[str, Param] = {
                "slurm_partition": _PARTITION,
                "timeout_min": _TIMEOUT_MIN,
                "cpus_per_task": spec.cpus,
                "mem_gb": spec.mem_gb,
                "slurm_max_num_timeout": resubmits,
                # Node-local scratch dodges the 99-char MrBayes path cap; JVM heap
                # from this job's mem. ponytail: XMX==mem_gb, drop headroom if OOM.
                "slurm_setup": [
                    "export PCH_SCRATCH=/tmp/pch.$SLURM_JOB_ID",
                    f"export PCH_ASTRAL_XMX={spec.mem_gb}g",
                ],
            }
            if spec.dep_labels:
                dep_ids = ":".join(jobs[label].job_id for label in spec.dep_labels)
                params["slurm_additional_parameters"] = {
                    "dependency": f"{spec.dep_mode}:{dep_ids}"
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
