# Tasks

Task tracking for PCH-ASTRAL.

Migrate legacy bash inference to the config-driven CLI. **Plan:** [`progress/plans/2026-06-22-inference-cli-migration.md`](plans/2026-06-22-inference-cli-migration.md) · **Agent-team split:** [`…-agent-team.md`](plans/2026-06-22-inference-cli-agent-team.md). Architecture: `docs/ARCHITECTURE.md`. References: `docs/HOW_TO_RUN.md`, `specs/cli_specs/human_specs.md`.

## In progress

- **PR 1 — Decouple inference** (`impl/decouple-inference`) — **Plan:** [`progress/plans/2026-07-05-decouple-inference.md`](plans/2026-07-05-decouple-inference.md). Make inference a generic `(csv → entry keyed by dataset_id=path)` unit: drop the inline sim keys + FN/FP from the entry (sim keys become a join, scoring a separate `pch experiment score` step). Real (Indo-European) datasets stop being a special case. Prereq for the SLURM fan-out.

## To do

- [ ] **PR 2 — SLURM fan-out** — **Plan:** [`progress/plans/2026-07-05-slurm-fanout.md`](plans/2026-07-05-slurm-fanout.md). Partition the dataset list into per-batch/condition jobs running `pch experiment inference --datasets …`, `afterany`-resubmit for the 4h cap, single final compact. Core code change: shard-aware + torn-line-tolerant `completed_runs`/`compact`. `pch experiment submit` (always-return) + `status` (expected vs done). Depends on PR 1.
- [ ] **M4** — wASTRAL + TREE-QMC runners (binary-interface discovery). Adds `PCH_WASTRAL`/`PCH_W_TREE_QMC`. Wire ASTRAL3's `bipartition_strategies` further (implement the `BINARY_CHARACTER` source — currently raises `NotImplementedError`).

**Docs are a per-milestone deliverable** — each milestone updates `docs/ARCHITECTURE.md` + the relevant `docs/` file and the `CLAUDE.md` index for what it shipped.

## Followups

- [ ] On-disk variant disambiguation: the ASTRAL3 output folder is a flat `PCH_W_ASTRAL3`, so two runs with different `bipartition_strategies` into the same `output_dir` collide (last-writer-wins on disk; the registry still keeps both rows via `config_hash`). Add a per-config identifier subfolder — but a raw sha256 `config_hash` isn't human-friendly. Instead require each config type to define a **human-readable label/slug** (e.g. `mp4-ga`) and use it in the path (`PCH_W_ASTRAL3/<label>/trees/…`). Left for when multi-variant runs are real; registry is the source of truth until then.
- [ ] Tiny end-to-end integration test (run every method through `pch experiment inference` vs a reference; cache binary install; compare FN/FP + registry shape). Would catch the bugs live-testing found.
- [ ] **GA long-scratch-path hardening**: MrBayes 3.2.7a caps input filenames at 99 chars; `runGA.sh` passes `$PCH_SCRATCH/tmp_mb_<runid>.nex`, so a long `PCH_SCRATCH` (e.g. 173-char CI scratch) trips `Error when setting parameter "Filename" (2)` and GA produces no trees. GA works with a normal-length scratch (verified end-to-end: real tree + branch lengths/supports). Harden: `runGA.sh` should `cd "$PCH_SCRATCH"` and pass a relative `tmp_mb_<runid>.nex` so the path stays short regardless of scratch depth (SLURM scratch can also be long).
- [ ] **ASTRAL3 heap** (smoke test): 320 chars → 410165 weighted quartets (each char's quartets emitted `weight`≈50×) OOMs the default 8g; needs `PCH_ASTRAL_XMX≥12g` or fewer chars. (The polytomy blocker — ASTRAL `-f` rejecting non-binary extra trees — is fixed: `utils.resolve_polytomies` seeded-refines every tree in `getResultBipartitions`, with tests. Safe because `-f` trees only seed the search space X, scored out by the quartets.)
- [ ] **Standardize on one phylo module / consider DendroPy**: the repo is uniformly Bio.Phylo (11 files, only phylo dep) — keep it for now (`resolve_polytomies` is ~12 lines, no dep needed). DendroPy is the richer research-standard (built-in `resolve_polytomies`, RF distances, tree comparisons) — evaluate a migration if tree-manipulation needs grow beyond Bio.Phylo's thin API; not worth an 11-file rewrite today.
- [ ] Deferred: inline `runASTRAL3.sh` (two Python steps + one `java`) into `ASTRAL3Runner` when the runner protocol grows a `run()` beyond `build_argv` (noted in `SCRIPT_CONTRACTS.md`).
- [ ] Reconcile stale downstream branches M4 (#21) + refactor (#22) onto the final M1/M2/M3.

## Done

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
