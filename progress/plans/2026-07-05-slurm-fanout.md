> **SUPERSEDED** — the shipped design uses submitit (not hand-rolled sbatch). Canonical: [specs/cli_specs/slurm_fanout_spec.md](../../specs/cli_specs/slurm_fanout_spec.md). This draft predates that decision.

# PR 2 — SLURM fan-out over the generic inference unit

**Prerequisite: PR 1** (inference = a dataset list → generic entries, resumable). SLURM then just **partitions the dataset list into jobs**, respects the 4 h cap via resumable resubmission, and compacts once. There is no "condition" concept inside inference — the launcher partitions *paths*.

## Shape (decided in the design interview)
- **Unit of parallelism:** a job runs a **batch of datasets** — all methods per dataset, topo, in-process. **No cross-job method dependency** (ASTRAL3←MP4/GA is handled inside the job). Granularity = batch/condition-level, **not** per-dataset (avoids flooding `secondary`).
- **Partition:** the *launcher* chooses — for the sim study, group by condition folder (`{poly}_{homoplasy}_{height}_{chars}`, human-readable job names); generally, chunk by size. The CLI takes a **neutral selector**, not a sim "condition."
- **Timeout:** `afterany`-resubmit each batch-job K times; the scheduler skips done units on resume. (ASTRAL ≈ 30–60 min/dataset dominates → a batch of ~20 needs several 4 h chunks; size K to expected runtime, or the human re-runs `submit` to top up.)
- **Compact:** batch-jobs write shards only; **one final compact job** (`afterany` on every chain tail) merges → registry + manifest.
- **Score:** a final `pch experiment score` job (PR 1), `afterany` on compact, when it's a sim study.

## CLI additions
- `pch experiment inference SPEC --datasets @batch.txt` (or `--shard i/N`) — run only the listed datasets (a neutral filter `path in batch`, not a "condition").
- `--no-compact` — write shards, skip the end-of-run compact (the final job compacts).
- `pch experiment submit SPEC` — the launcher: emit sbatch per batch, wire the resubmit chains + the final compact/score. **Always returns** (async). `--dry-run` writes the scripts without submitting (the unit-testable surface).
- `pch experiment status EXPERIMENT` — extend to **expected** (dataset list × enabled methods) vs **done** (OK entries), per method. Reads shards, so it's accurate mid-run — the "how done am I" + "what's left."

## The one real code change: shard-aware, torn-line-tolerant resume
Under `--no-compact` the compacted registry is empty for the whole run, so **`completed_runs` must read shards + the registry** — otherwise a resubmission (empty registry) redoes everything, and (at any future array scale) a dependent sees no upstream. A 4 h SIGKILL leaves a **torn trailing line** (a >8 KB newick row spans multiple `write()` calls); **both `completed_runs` and `compact` must `try/except` per line and skip an undecodable tail** (today `if not line.strip()` skips only *empty* lines → a torn line crashes `json.loads`). This is the load-bearing change; fully unit-testable without SLURM.

## Concurrency correctness (parallel batch-jobs share one experiment folder)
- **shards** — per-job-id (`SLURM_JOB_ID` / `ARRAY_JOB_ID_TASKID`), one writer, append-only, lock-free (already). Reads tolerate torn tails (above).
- **manifest** — batch-jobs must **not** touch `manifest.json` (concurrent `init`/`finalize` = truncate-write race → truncated-read crash). The **final compact** writes the single manifest (methods, tally, timestamps).
- **compact** — the single final job: **atomic write** (temp + `rename`), `cleanup=False` → verified delete, and it must depend `afterany` on **every** resubmit-chain tail (else it deletes shards a still-pending job needs = silent data loss). **Retry/resubmit the compact job too** — don't leave it a single un-retried chokepoint (a killed mid-write compact today truncates the registry with nothing to re-run it).

## Launcher hardening (from the plan review)
- `JOBID=$(sbatch --parsable …)` for robust id capture; guard an empty capture (a failed sbatch → malformed `--dependency`).
- `afterany` (not `afterok`) for the resubmit chains — a 4 h timeout is a non-zero exit, so `afterok` would stall the chain forever.
- Resources (mem/cpu/time/partition) via **launcher flags**, not bash-parsing the YAML.
- *If arrays are ever used at scale:* `--array=…%N` throttle (512 G × N is unschedulable), 1-based `SLURM_ARRAY_TASK_ID`→dataset mapping + `MaxArraySize`, explicit `--no-requeue`.

## Explicitly not needed now (deferred)
Array-per-method / `aftercorr` / cross-job method `--dependency` — method deps are in-process within a batch-job. Add SLURM arrays only if condition-level parallelism proves insufficient. (Note if we ever do: `aftercorr` is the element-wise primitive, but it does **not** compose with resubmit chains — which is exactly why the shard-aware gate stays.)

## Observability at scale (the C5 decision)
Blocked/failed runs are **logged** (per-job `.out` + the method's `log_path`), **not** registry rows. `pch experiment status` (expected vs done) surfaces the gaps; the human re-runs `submit` to top up. The plan/launcher must name where `.out` lands (`SLURM_OUT/`).

## Phases
1. **Shard-aware + torn-line-tolerant `completed_runs`/`compact`** — the core change; ships value locally (crash-safe compact, resume across kills).
2. `--no-compact` run mode + the `--datasets`/`--shard` selector.
3. `pch experiment status` expected-vs-done.
4. The launcher + `--dry-run` (unit-tested: `#SBATCH` headers, the `--dependency` chain, the final compact-then-score wiring).
5. Cluster smoke test (one small experiment end-to-end).

## Locked (from the interview)
- Granularity = condition/batch-level, not per-dataset.
- One experiment folder at a time; no config-rerun → the config-blind-gate hazard doesn't arise.
- Top-up model: `submit` is always-return + idempotent; the human re-fires until `status` says complete.
