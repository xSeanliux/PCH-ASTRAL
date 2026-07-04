# Tasks

Task tracking for PCH-ASTRAL.

Migrate legacy bash inference to the config-driven CLI. **Plan:** [`progress/plans/2026-06-22-inference-cli-migration.md`](plans/2026-06-22-inference-cli-migration.md) · **Agent-team split:** [`…-agent-team.md`](plans/2026-06-22-inference-cli-agent-team.md). Architecture: `docs/ARCHITECTURE.md`. References: `docs/HOW_TO_RUN.md`, `specs/cli_specs/human_specs.md`.

## In progress

- **M3** (#20, `impl/m3-ga-astral3`) — GA + ASTRAL3 runners **present + runnable**. Scoped down: scheduling (dependency ordering/gating) split out to its own PR. Awaiting merge.

## To do

- [ ] **Scheduling** (own PR — split out of M3) — cross-run dependency handling: when MP4/GA/ASTRAL3 run as separate invocations, order dependents after upstreams and gate on upstream success (check the registry). In SLURM, translate to `--dependency` between jobs. Removed from M3 as too complex (was: co-requisite check, in-memory status gate, `dependencies()` + `missing_prerequisites`, topo-sort). Re-derive cleanly here; today a missing input just fails the run.
- [ ] **M4** — wASTRAL + TREE-QMC runners (binary-interface discovery). Adds `PCH_WASTRAL`/`PCH_W_TREE_QMC`. Wire ASTRAL3's `bipartition_strategies` further (implement the `BINARY_CHARACTER` source — currently raises `NotImplementedError`).
- [ ] **M5** — Pipeline executor + SLURM, concurrency-safe reruns (replace `run_parallel_sim.sh`). Depends on **Scheduling**.

**Docs are a per-milestone deliverable** — each milestone updates `docs/ARCHITECTURE.md` + the relevant `docs/` file and the `CLAUDE.md` index for what it shipped.

## Followups

- [ ] Tiny end-to-end integration test (run every method through `pch experiment inference` vs a reference; cache binary install; compare FN/FP + registry shape). Would catch the bugs live-testing found.
- [ ] Deferred: inline `runASTRAL3.sh` (two Python steps + one `java`) into `ASTRAL3Runner` when the runner protocol grows a `run()` beyond `build_argv` (noted in `SCRIPT_CONTRACTS.md`).
- [ ] Reconcile stale downstream branches M4 (#21) + refactor (#22) onto the final M1/M2/M3.

## Done

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
