# Tasks

Task tracking for PCH-ASTRAL.

Migrate legacy bash inference to the config-driven CLI. **Plan:** [`progress/plans/2026-06-22-inference-cli-migration.md`](plans/2026-06-22-inference-cli-migration.md) · **Agent-team split:** [`…-agent-team.md`](plans/2026-06-22-inference-cli-agent-team.md). Architecture: `docs/ARCHITECTURE.md`. References: `docs/HOW_TO_RUN.md`, `specs/cli_specs/human_specs.md`.

## In progress

- **PR 1 — Decouple inference** (`impl/decouple-inference`) — **Plan:** [`progress/plans/2026-07-05-decouple-inference.md`](plans/2026-07-05-decouple-inference.md). Make inference a generic `(csv → entry keyed by dataset_id=path)` unit: drop the inline sim keys + FN/FP from the entry (sim keys become a join, scoring a separate `pch experiment score` step). Real (Indo-European) datasets stop being a special case. Prereq for the SLURM fan-out.

## To do

- [ ] **M4** — wASTRAL + TREE-QMC runners (binary-interface discovery). Adds `PCH_WASTRAL`/`PCH_W_TREE_QMC`. Wire ASTRAL3's `bipartition_strategies` further (implement the `BINARY_CHARACTER` source — currently raises `NotImplementedError`).

**Docs are a per-milestone deliverable** — each milestone updates `docs/ARCHITECTURE.md` + the relevant `docs/` file and the `CLAUDE.md` index for what it shipped.

## Followups

- [ ] On-disk variant disambiguation: the ASTRAL3 output folder is a flat `PCH_W_ASTRAL3`, so two runs with different `bipartition_strategies` into the same `output_dir` collide (last-writer-wins on disk; the registry still keeps both rows via `config_hash`). Add a per-config identifier subfolder — but a raw sha256 `config_hash` isn't human-friendly. Instead require each config type to define a **human-readable label/slug** (e.g. `mp4-ga`) and use it in the path (`PCH_W_ASTRAL3/<label>/trees/…`). Left for when multi-variant runs are real; registry is the source of truth until then.
- [ ] Tiny end-to-end integration test (run every method through `pch experiment inference` vs a reference; cache binary install; compare FN/FP + registry shape). Would catch the bugs live-testing found.
- [ ] **Standardize on one phylo module / consider DendroPy**: the repo is uniformly Bio.Phylo (11 files, only phylo dep) — keep it for now (`resolve_polytomies` is ~12 lines, no dep needed). DendroPy is the richer research-standard (built-in `resolve_polytomies`, RF distances, tree comparisons) — evaluate a migration if tree-manipulation needs grow beyond Bio.Phylo's thin API; not worth an 11-file rewrite today.
- [ ] Deferred: inline `runASTRAL3.sh` (two Python steps + one `java`) into `ASTRAL3Runner` when the runner protocol grows a `run()` beyond `build_argv` (noted in `SCRIPT_CONTRACTS.md`).
- [ ] **SLURM fan-out followups** (from PR 2): auto-size `--resubmits` from recorded `runtime_seconds`; (condition, method) jobs → submitit **job arrays** (`map_array`) if job counts get high; confirm the cluster's node-local `/tmp` policy (size/cleanup) when access exists; live-cluster smoke (submitit `LocalExecutor`/`DebugExecutor` stand in for now).
- [ ] Durability: `handle_score` holds all results in memory and writes once at the end, so an interrupted run loses every score computed so far (the file itself is safe — write-then-`os.replace`). Periodic flush or a shard-per-run would make long passes resumable mid-flight.
- [ ] **Network simulation** — simulate under networks with reticulation, not just trees. `data/base_networks/` and the spec's `n_horizontal_edges` already exist (`net{edges}-{tree}.txt`, `A=0` = plain tree); close the gap so non-zero reticulation exercises a real network model end to end.
- [ ] **Zip + checkpoint experiment results** — an experiment folder is self-contained but grows large (trees, logs, shards) and is untracked. Add an archive/restore step so a finished run can be snapshotted, moved off scratch, and restored for re-analysis without a rerun.
- [ ] Reconcile stale downstream branches M4 (#21) + refactor (#22) onto the final M1/M2/M3.

## Done

- [x] **Parallelize `pch experiment score`** — `-t/--threads N` scores N estimates concurrently. A thread pool (not a process pool) fits: each score is an `Rscript` subprocess, so it is I/O-bound rather than GIL-bound, and threads keep `resolve_reference_newick`'s `lru_cache` shared instead of needing a per-process re-warm. Dedup moved ahead of the fan-out so workers never race the `already` set. Measured on 64 real rows: 159.6s → 21.2s at `-t 16` (7.5x), byte-identical output.
- [x] **`handle_score` within-run dedup** — a duplicate sim-registry `path` row fanned the inf⨝sim join out, so `score()` ran twice and `scores.csv` got duplicate `(dataset_id, method, config_hash)` rows. Now skips a key once scored in the same run (regression test in `test_handle_score.py`). Surfaced by the model-condition sweep notebook (`scripts/pynb/model_condition_sweep.ipynb`: FN-by-parameter + runtime-by-char-count).
- [x] **PR 2 — SLURM fan-out** — **Spec (canonical):** [`specs/cli_specs/slurm_fanout_spec.md`](../specs/cli_specs/slurm_fanout_spec.md) · **Earlier draft (superseded):** [`progress/plans/2026-07-05-slurm-fanout.md`](plans/2026-07-05-slurm-fanout.md). `pch experiment inference --executor slurm` fans out one submitit job per (condition, method): method deps → `afterok` edges, final `afterany` compact job, requeue-on-timeout for the 4 h `secondary` cap, heavy/light resource tiers (ASTRAL3 vs MP4/GA), node-local scratch. Shard-aware + torn-line-tolerant `compact`/`completed_runs`; `--datasets`/`--method` filters; `--dry-run` prints the DAG (no `sbatch` needed; missing `sbatch` otherwise errors). Also closed: **CLI yaml-vs-folder arg inconsistency** (all `experiment` subcommands now take the spec yaml), **GA long-scratch-path hardening** (`runGA.sh` `cd $PCH_SCRATCH` + relative nexus), **thin `experiment status`** (now expected-vs-done gap view), **ASTRAL3 heap** (heavy tier sets `PCH_ASTRAL_XMX` from the job's `mem_gb`; `--astral-mem-gb` overrides).
- [x] **Scheduler** (#23, merged to `main`) — `dependencies()` on runners, topological order, `scheduler.completed_runs` ledger (skip already-done, block on missing upstreams, record only successes). OK-only registry; manifest keeps first `created_at` + a run tally.
- [x] **M3** (#20, merged to `main`) — GA + ASTRAL3 runners present + runnable; `runners/` package; config-class enablement; `PCH_W_ASTRAL3` folder; `bipartition_strategies` → `-S`. (Scheduling deliberately split out → the Scheduler PR.)
- [x] **M0** — Script hardening + `docs/SCRIPT_CONTRACTS.md`.
- [x] **M1** (#18) — Three-layer scaffolding: Python API (`infer → InferenceResult`), `method_config` registry, `Runner` Protocol + `RUNNERS`, atomic `pch infer`, shard→`compact`→joinable `inference_registry.csv` + `manifest.json`, `pch experiment status`. Review: every comment addressed in-PR (see below).
- [x] **M2** (#19) — Atomic `score`/`summarize` object API (`ScoreResult`); FN/FP in the registry; `ConsensusMethod` StrEnum. (`query`/`get` deferred — CSV is directly joinable.)
- [x] **M3** hardening (kept after scope-shrink) — `runners/` package split (`base`/`mp4`/`ga`/`astral3`), config-class enablement (`config_for`, no field-name table), `bipartition_strategies` → `-S` sources, `$PCH_ASTRAL_XMX` heap, `runASTRAL3.sh` correctness (exit code, no pre-truncate, no log-clobber). (Scheduling machinery — `dependencies`/`missing_prerequisites`/gate/co-requisite — removed; see To do.)
- [x] `consensus_method` modeled as `ConsensusMethod` StrEnum (in `lib/inference/inference.py`).
- [x] Document inference methods in `docs/KEYS.md`; catalogue legacy scripts in `docs/HOW_TO_RUN.md`; `docs/` index + `docs/ARCHITECTURE.md` in `CLAUDE.md`.

### PR #18 (M1) review — every comment addressed in-PR

- Schema in `scripts/py/cli/schemata.py`; reusable `CONFIG_KEY`/`MODEL_NETWORK_KEY` groups → sim/config/dataset/inference CSVs joinable. Row is a `RegistryRow` TypedDict (was `dict[str, object]`).
- Runners modeled as classes: `Runner` Protocol + `MP4Runner` (static, stateless methods) + `RUNNERS` registry; `api.infer` dispatches via `RUNNERS[method]`.
- Registry concurrency: shard-per-SLURM-job (one `.jsonl` writer per job, lock-free; flock rejected for NFS/Lustre) + `compact` (merges, dedups last-writer-wins, seeds from existing registry, deletes shards). `run_key` human-readable; sha256 only (no sha1).
- `status` → `RunStatus` StrEnum (`ok`|`failed`); `to_registry_row` emits `.value`.
- `ran_at` ISO8601 (no bare nanos); `log_path` = merged stdout+stderr.
- `resolve_config` returns `MethodConfigT` union (was `BaseModel`).
- `methods.py` → `method_config.py`.
- Removed `--output-json` (redirect `--json` instead); `pch experiment inference` prints the registry path.
- Operations doc: `docs/CLI.md`.
