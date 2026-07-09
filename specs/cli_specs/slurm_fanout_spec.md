# Spec — SLURM fan-out for `pch experiment`

Status: **draft** (iterating). Branch when implemented: `impl/slurm-fanout` (off `main`).
Source plan: `~/.claude/plans/fancy-waddling-lighthouse.md`.

## Context

Inference is a generic, path-keyed unit (PR #24): `pch experiment inference SPEC` iterates the sim registry × methods (topo order, ASTRAL after MP4/GA), writes lock-free per-job JSONL **shards**, and `compact` merges them into `inference_registry.csv`. Real workloads are hundreds–thousands of datasets × ~5 methods on a SLURM cluster whose `secondary` queue caps jobs at **4 h**, while ASTRAL alone is ~30–60 min/dataset. We fan the work out across jobs, absorb the 4 h cap by resubmission, and compact once at the end — without a cross-job dependency graph (method deps stay in-process). We also fix the yaml-vs-folder arg inconsistency and the GA/MrBayes 99-char filename cap that a long SLURM scratch path trips.

Decisions locked with user: **(1)** spec YAML is the arg for *every* `experiment` subcommand, spec lives in the experiment folder; **(2)** partition = **one submitit job per (condition, method)**, requeue-on-timeout for the 4 h cap; **(3)** fold the GA long-path fix into this work.

No SLURM cluster available → the launcher must be fully exercisable via `--dry-run` + unit tests + a local multi-shard end-to-end. Live-cluster smoke deferred.

## Design

### A. Shard-aware, crash-tolerant registry/scheduler (`registry.py`, `scheduler.py`)
Load-bearing. A 4 h SIGKILL can tear a shard's trailing line (a >8 KB newick row spans multiple `write()`s); between resubmits nothing has compacted yet.
- Add `registry._iter_shard_rows(experiment_folder) -> Iterator[dict]` — reads `shards/*.jsonl` (sorted), `try/except json.JSONDecodeError` per line, **skips an undecodable line** (torn tail). `registry.py:105–114`.
- `registry.compact` uses `_iter_shard_rows` (currently raw `json.loads` per line → crashes on a torn line). `registry.py:86–124`.
- `scheduler.completed_runs` reads **registry.csv ∪ shards** (via `_iter_shard_rows`), not just the compacted CSV — else a resubmitted job (empty/stale registry) redoes finished datasets and a dependent sees no upstream. Keep the `status == ok` filter + `(method, config_hash)` set shape. `scheduler.py:30–44`.

### B. Run-mode flags on `pch experiment inference` (`handle_inference.py`, `main.py`)
- `--datasets PATH` — text file of dataset paths (one per line). The sim registry has one row per dataset; `handle_inference` reads all rows (`:37`) then loops every one (`:52`). This flag **drops the rows whose `canonical_path` isn't in the file**, so the job processes only that subset (e.g. one condition's datasets). Default = no filter = all rows (unchanged behavior).
- `--method M` — restrict the run to a single enabled method (mirrors `--datasets`, filters the inner method loop `:63`). Used by the per-(condition, method) fan-out so each job runs exactly one method; also handy manually. Default = all enabled methods.
- **`no_compact` is internal, not a user flag** — a param on the inference body that the SLURM executor sets (batch jobs write shards, don't compact; only the final compact job merges). Skips `compact()` + `finalize_manifest()` when set. `handle_inference.py:100–101`.
- Manifest race fix (falls out of the above): only a compacting run touches `manifest.json` (concurrent init/finalize = truncate-write race). Move `init_manifest` out of the per-job path; the final compact writes the manifest. `handle_inference.py:48,100`.

### C. SLURM via **submitit** — executor abstraction (`executor.py` NEW, `handle_inference.py`, `main.py`)
The original migration plan (M5, `progress/plans/2026-06-22-inference-cli-migration.md:571`) chose **submitit** — "use submitit, don't hand-roll" — because it owns SLURM arrays, dependency chains, and **requeue-on-timeout** (exactly the 4 h-cap rerun). The jinja/sbatch launcher is that plan's documented *fallback if submitit doesn't fit the cluster*; not built now. `pyslurm` (compiled per SLURM version) / `slurmrestd` (daemon + tokens) are rejected for the same reasons.

- `scripts/lib/inference/executor.py` **(NEW)** — just `SlurmExecutor` (no `LocalExecutor` class: `--executor local` is the existing inline loop, untouched — a one-impl abstraction isn't worth it). Wraps `submitit.AutoExecutor`; per-job `update_parameters(slurm_partition="secondary", timeout_min=240, cpus_per_task=…, mem_gb=…, slurm_max_num_timeout=K)`. **Requeue-on-timeout replaces the afterany-K chain**: a timed-out job auto-requeues; idempotent `completed_runs` skip makes the rerun safe. So no explicit resubmit chains, `--parsable` parsing, or job-id wiring.
  - Jobs run a top-level picklable `run_batch(spec_path, datasets_file, method)` that reloads the config and calls the inference body over that (dataset subset, single method) with `no_compact` set. Args are paths/str (picklable, importable) — no Pydantic-over-pickle.
- Fold into `inference` (no separate `submit` command): `pch experiment inference SPEC --executor local|slurm [--dry-run] [--resubmits K] [--astral-mem-gb N]`. `--executor local` (default) = today's inline run + compact. `--executor slurm` fans out and returns.
- Partition by **(condition, method)** — condition = `Path(row["path"]).parent.name` (matches `run_parallel_sim.sh`). One submitit job per method per condition: `run_batch(spec, <condition>.txt, method)` over that condition's dataset list (written to `<folder>/inference_data/batches/<condition>.txt`).
- **Per-method resources = 2 tiers** (not a full map): `heavy` (ASTRAL3 — big `mem_gb`/heap, via `--astral-mem-gb`) vs `light` (MP4/GA — small default). So ASTRAL schedules with the memory it needs while MP4/GA stay cheap on `secondary`, and only the slow ASTRAL job chains against the 4 h cap. Each job exports short node-local `PCH_SCRATCH=/tmp/pch.$SLURM_JOB_ID` (dodges the 99-char cap) + `PCH_ASTRAL_XMX` from its `mem_gb`.
- **Method deps = submitit `afterok` edges.** Within a condition, `Runner.dependencies(cfg)` gives MP4,GA→ASTRAL3; submit MP4/GA first, then the ASTRAL3 job with `slurm_additional_parameters={"dependency": f"afterok:{mp4.job_id}:{ga.job_id}"}`. submitit hands back `job.job_id` (no `--parsable`/parse/guard) and owns submit+requeue, so this is ~1 line/edge, not a hand-rolled chain. ASTRAL3 reads MP4/GA's on-disk trees once its deps succeed. A genuinely failed upstream ⇒ `afterok` cancels ASTRAL3 (correct: no bipartitions → no heuristic run; mirrors the old in-process "blocked").
- Final **compact** job depends `afterany` on **all** method jobs; it writes the manifest.
- `--dry-run` — submitit `DebugExecutor` / print the submission spec (jobs + afterok edges + resources), no live submit. `--executor slurm` with no SLURM (submitit reports no sbatch) → error unless `--dry-run` (no local-degrade; that's `--executor local`).
- `--resubmits K` (→ `slurm_max_num_timeout`) default **3**; overridable. Auto-sizing from recorded `runtime_seconds` deferred.

### D. `pch experiment status SPEC` — expected vs done (rewrite `handle_status.py`)
Replace the flat run-tally with a gap view: **expected** = sim datasets × enabled methods (spec `methods:`); **done** = `completed_runs` (now shard-aware). Print per-condition done/expected per method + list what's missing.

### E. Arg-UX unification (`main.py`, `docs/CLI.md`)
All `experiment` subcommands take the spec **yaml**. Change `status`/`compact` from folder-arg to yaml-arg, deriving the folder via `_get_experiment_config(spec).experiment_folder`. Recommend/document the spec living in the experiment folder. Update the CLI.md arg-convention callout (now uniform).

### F. GA long-path fix (`scripts/sh/runGA.sh`)
`cd "$PCH_SCRATCH"` and pass a **relative** `tmp_mb_$RUNID.nex` (adjust the `commandLineNex.R` / `mb` / `mv Bayes_out_*` lines) so the MrBayes input path stays < 99 chars regardless of scratch depth. Keep the `Bayes_out_*` cleanup.

## Files
- `scripts/lib/inference/registry.py` — `_iter_shard_rows` (torn-line), compact uses it.
- `scripts/lib/inference/scheduler.py` — shard-aware `completed_runs`.
- `scripts/lib/inference/executor.py` **(NEW)** — `SlurmExecutor` (submitit) + top-level `run_batch`. (No `LocalExecutor` class; local = the existing inline loop.)
- `scripts/py/cli/handle_inference.py` — `--datasets`, `--method`, internal `no_compact`, manifest gating, executor dispatch, (condition, method) partition + per-condition `afterok` DAG.
- `scripts/py/cli/handle_status.py` — rewrite to expected-vs-done.
- `scripts/py/cli/main.py` — `inference` `--executor`/`--resubmits`/`--datasets`/`--method`/`--astral-mem-gb` flags; `status`/`compact` → yaml arg.
- `scripts/sh/runGA.sh` — cd + relative nexus.
- `pyproject.toml` — add `submitit` dep (pure-Python, pip).
- `docs/CLI.md`, `progress/tasks.md` — SLURM/executor section, arg unification, close followups.

## Reuse (don't rebuild)
- `registry.canonical_path` (`registry.py:61`) for `--datasets` matching + condition grouping.
- `registry.compact` / `write_result` / `current_shard_id` (`registry.py:49,76,86`) — unchanged mechanism.
- `scheduler.completed_runs` / `topological_order` (`scheduler.py:30,47`) — extend, don't replace.
- `_get_experiment_config` (`main.py`) for yaml→config in status/compact.
- `Runner.dependencies(cfg)` (used in `handle_inference.py:72–84`) — the method DAG. `--executor local` uses it in-process; `SlurmExecutor` reads the same edges to wire the per-condition `afterok` deps. Single source of truth either way.

## Parallel execution (PM dispatch)

Structured for a PM agent to fan out subagents. Two rules make it safe: **(1) disjoint file ownership** — every file has exactly one owning package, so no two agents ever edit the same file; **(2) contracts locked before dispatch** — the PM fixes the signatures below first, and every agent codes against them, so parallel work composes without integration drift.

### Contracts (lock these first — no code until agreed)
- `registry._iter_shard_rows(folder: Path) -> Iterator[dict]` — torn-line-tolerant shard reader.
- `scheduler.completed_runs(folder: Path) -> dict[DatasetKey, set[tuple[str,str]]]` — **signature unchanged**, impl now reads registry ∪ shards.
- `handle_inference(config, *, datasets: Path | None = None, method: str | None = None, no_compact: bool = False) -> Path` — inline body; new kwargs are additive.
- `executor.run_batch(spec_path: str, datasets_file: str, method: str) -> None` — picklable job body (calls `handle_inference(..., no_compact=True)`).
- `executor.SlurmExecutor(config).fan_out(rows, *, resubmits: int, astral_mem_gb: int | None, dry_run: bool) -> list[Job]` — partitions (condition, method), wires `afterok`, submits + compact job.
- `handle_status(config) -> None` — expected-vs-done gap view.

### Dispatch DAG (waves = dependency barriers; packages within a wave run in parallel)

**Wave 1 — foundations** (3 parallel, zero shared files)
- **P1 · `registry.py`** — `_iter_shard_rows` + make `compact` use it (torn-line). Test: truncated tail skipped, rest merges.
- **P2 · `scripts/sh/runGA.sh`** — `cd $PCH_SCRATCH` + relative nexus. Test: 3-method smoke with a >99-char `PCH_SCRATCH` (GA survives).
- **P3 · `pyproject.toml`** — add `submitit`; `uv sync`. Trivial; unblocks P6.

**Wave 2 — build on foundations** (2 parallel)
- **P4 · `scheduler.py`** — `completed_runs` reads registry ∪ shards (needs P1). Test: uncompacted shard rows are seen.
- **P5 · `handle_inference.py`** — `datasets`/`method` filters, internal `no_compact`, manifest-gating. Test: subset filter; `no_compact` leaves shards intact + manifest untouched.

**Wave 3 — executor + status** (2 parallel)
- **P6 · `executor.py` (NEW)** — `SlurmExecutor` + `run_batch` (needs P5 signature, P3 submitit, reused `Runner.dependencies`/`topological_order`). Test: DAG under submitit `DebugExecutor` (per-(condition,method) jobs, `afterok:<mp4>:<ga>`, compact `afterany` on all, heavy/light tiers).
- **P7 · `handle_status.py`** — expected-vs-done (needs P4). Test: gap math on a partial registry.

**Wave 4 — integration** (1 agent; sole owner of `main.py` + docs)
- **P8 · `main.py`, `docs/CLI.md`, `progress/tasks.md`** — wire `inference` flags (`--executor`/`--datasets`/`--method`/`--resubmits`/`--astral-mem-gb`) + executor dispatch (slurm → `SlurmExecutor.fan_out`, else inline); `status`/`compact` → yaml arg; docs; close followups. Needs P5·P6·P7. Test: local end-to-end + `DebugExecutor` fan-out == single-process run; `make py-test py-static py-lint`.

### File-ownership map (one owner each — the anti-collision guarantee)
`registry.py`→P1 · `runGA.sh`→P2 · `pyproject.toml`→P3 · `scheduler.py`→P4 · `handle_inference.py`→P5 · `executor.py`→P6 · `handle_status.py`→P7 · `main.py`+`docs/`+`tasks.md`→P8.

### PM playbook
1. Lock the contracts above (edit signatures only, no logic) so every agent has stable interfaces.
2. Dispatch Wave 1 (P1·P2·P3) in parallel → each returns with its file + passing unit test.
3. Barrier, then Wave 2 (P4·P5), Wave 3 (P6·P7) — parallel within each wave.
4. Wave 4 (P8) integrates + runs the full gate. Each package is independently reviewable (small, single-file, self-tested); the PM reviews at each barrier before releasing the next wave.

## Verification (no cluster needed)
- **Unit tests**: torn-line (truncated last line → `compact`/`completed_runs` skip it, keep rest); shard-aware `completed_runs` (uncompacted shard rows seen); `--datasets` subset + `--method` filter; internal `no_compact` leaves registry uncompacted + shards intact + manifest untouched; `status` expected-vs-done math; `SlurmExecutor` DAG under `--dry-run` (partition=`secondary`, `timeout_min=240`, `slurm_max_num_timeout=K`, one job per (condition, method), ASTRAL3 job carries `afterok:<mp4>:<ga>`, compact `afterany` on all, heavy/light resource tiers applied).
- **Fan-out end-to-end (SLURM stand-in, real execution)**: `inference SPEC --executor local` over the smoke experiment == today's inline run; then drive `SlurmExecutor` against **submitit's** `LocalExecutor`/`DebugExecutor` (`cluster="local"/"debug"`) so the per-(condition, method) `run_batch` jobs run as local subprocesses honoring `afterok` order, + the dependent compact → assert merged registry == a single-process run. Better than string-asserting sbatch.
- **Resume/torn-line**: run two batch jobs with `no_compact` (separate shards) then `compact` → merged == single run; truncate a shard's tail → still merges.
- **GA fix**: re-run 3-method smoke with short `PCH_SCRATCH` (still green) **and** a >99-char `PCH_SCRATCH` (GA now survives).
- `make py-test py-static py-lint` clean.
- Live-cluster smoke deferred (no SLURM yet); submitit `LocalExecutor` + `DebugExecutor` stand in.

## Resolved
- **Submission mechanism:** **submitit** (the original M5 choice), not hand-rolled sbatch. Requeue-on-timeout = the 4 h-cap handling; submitit's `LocalExecutor`/`DebugExecutor` = real no-cluster testing. jinja/sbatch kept only as a documented fallback.
- **K (resubmits):** `slurm_max_num_timeout`, default **3**, `--resubmits` overrides. Auto-sizing from `runtime_seconds` = deferred followup.
- **No SLURM:** `--executor slurm` errors unless `--dry-run`; local = `--executor local`.
- **Command shape:** folded into `inference --executor local|slurm`, no separate `submit` command.
- **Granularity:** per-**(condition, method)** job (not per-condition). Buys per-method resource sizing + isolated requeue; method deps become submitit `afterok` edges within each condition (cheap with `job.job_id`). Needs a `--method` filter. (The one deliberately non-minimal choice — per-condition in-process is simpler but loses the sizing/isolation.)
- **Simplicity trims:** no `LocalExecutor` class (local = existing inline loop); `no_compact` internal (not a user flag); per-method resources = 2 tiers (heavy ASTRAL / light rest), not a map.

## Open questions / iteration notes
- **submitit fit on the actual cluster** — unverifiable until cluster access. If it doesn't fit, fall back to the jinja/sbatch launcher (documented in the 2026-06-22 plan). Keep `SlurmExecutor` thin so the fallback is a drop-in.
- Per-method resource defaults (mem_gb/cpus for MP4/GA/ASTRAL3) — seed from the legacy sbatch (512G) then tune; expose overrides.
- (condition, method) jobs vs submitit **job arrays** (`map_array`) — arrays tidier at high counts; start with explicit submits, revisit.
- Dependency granularity: ASTRAL3[condition] waits on **all** of MP4[condition]+GA[condition] (condition-coarse). Per-dataset deps would be finer but aren't worth the extra jobs.
- Node-local `PCH_SCRATCH=/tmp/pch.$SLURM_JOB_ID`: confirm the cluster's node-local tmp policy (size, cleanup) when access exists.
- Auto-size `--resubmits` from recorded `runtime_seconds` (followup).
- **Verify on cluster: requeue-on-timeout is SLURM-native** — a requeued job retains its job id, so `afterok` dependents WAIT for the requeued run to succeed rather than being cancelled as never-satisfied when a job transiently hits the 4 h cap. This is the mechanism submitit's `slurm_max_num_timeout` relies on; confirm the cluster scheduler behaves this way before depending on it.
- **Relative paths and `--chdir`**: submitit pins `--chdir` to the submission cwd, so relative `experiment_folder`/dataset paths in batch files resolve identically on the worker node. The `dataset_id` (= relative input CSV path) stays relative — no re-keying needed.
