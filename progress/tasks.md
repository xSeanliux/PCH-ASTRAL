# Tasks

Task tracking for PCH-ASTRAL.

Migrate legacy bash inference to the config-driven CLI. **Plan:** [`progress/plans/2026-06-22-inference-cli-migration.md`](plans/2026-06-22-inference-cli-migration.md) · **Agent-team split:** [`…-agent-team.md`](plans/2026-06-22-inference-cli-agent-team.md). Architecture: `docs/ARCHITECTURE.md`. References: `docs/HOW_TO_RUN.md`, `specs/cli_specs/human_specs.md`.

## In progress

- **M3** (#20, `impl/m3-ga-astral3`) — GA + ASTRAL3 runners, order-dependent. Code + review fixes done; awaiting merge.

## To do

- [ ] **M4** — wASTRAL + TREE-QMC runners (binary-interface discovery). Adds `PCH_WASTRAL`/`PCH_W_TREE_QMC`. Wire ASTRAL3's `bipartition_strategies` further (implement the `BINARY_CHARACTER` source — currently raises `NotImplementedError`).
- [ ] **M5** — Pipeline executor + SLURM, concurrency-safe reruns (replace `run_parallel_sim.sh`). Use `runner.dependencies()` for `--dependency` job ordering (the 2b await hook).

**Docs are a per-milestone deliverable** — each milestone updates `docs/ARCHITECTURE.md` + the relevant `docs/` file and the `CLAUDE.md` index for what it shipped.

## Followups

- [ ] Tiny end-to-end integration test (run every method through `pch experiment inference` vs a reference; cache binary install; compare FN/FP + registry shape). Would catch the bugs live-testing found.
- [ ] `select_methods` raises `ValueError` on bad config → wrap as `typer.BadParameter` at the `experiment inference` command for a clean CLI error (R7, deferred).
- [ ] `_BaseRunner.missing_prerequisites` appends `None` if a dep's `group_estimate_path` is `None` (unreachable today — deps are only MP/GA). Guard if a `None`-group dependency ever appears.
- [ ] Deferred: inline `runASTRAL3.sh` (two Python steps + one `java`) into `ASTRAL3Runner` when the runner protocol grows a `run()` beyond `build_argv` (noted in `SCRIPT_CONTRACTS.md`).
- [ ] Reconcile stale downstream branches M4 (#21) + refactor (#22) onto the final M1/M2/M3.

## Done

- [x] **M0** — Script hardening + `docs/SCRIPT_CONTRACTS.md`.
- [x] **M1** (#18) — Three-layer scaffolding: Python API (`infer → InferenceResult`), `method_config` registry, `Runner` Protocol + `RUNNERS`, atomic `pch infer`, shard→`compact`→joinable `inference_registry.csv` + `manifest.json`, `pch experiment status`. Review: every comment addressed in-PR (see below).
- [x] **M2** (#19) — Atomic `score`/`summarize` object API (`ScoreResult`); FN/FP in the registry; `ConsensusMethod` StrEnum. (`query`/`get` deferred — CSV is directly joinable.)
- [x] **M3** review hardening — `api.failed_result` (unified FAILED rows), generic runner `dependencies()` (co-requisite + topo-order + gate), `runners/` package split, `bipartition_strategies` wired (mp4/ga), `$PCH_ASTRAL_XMX` heap, `runASTRAL3.sh` correctness (exit code, no pre-truncate, no log-clobber).
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
