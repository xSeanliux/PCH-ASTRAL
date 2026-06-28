# Tasks

Task tracking for PCH-ASTRAL.

## In progress

- [ ] Migrate legacy bash inference to the config-driven CLI. **Plan:** [`progress/plans/2026-06-22-inference-cli-migration.md`](plans/2026-06-22-inference-cli-migration.md) · **Agent-team split + gap review:** [`…-agent-team.md`](plans/2026-06-22-inference-cli-agent-team.md). References: `docs/HOW_TO_RUN.md`, `specs/cli_specs/human_specs.md`.

## To do

- [ ] **M0** — Script hardening & interface contracts + `docs/SCRIPT_CONTRACTS.md` (fix stale `printQuartets.py`, drop `~/scratch` hardcoding). See plan.
- [ ] **M1** — Three-layer scaffolding: Python API (`infer → InferenceResult`), `METHOD_CONFIG` registry, atomic `pch infer --method mp4`, pipeline slice. Artifact model: `.parts`→`compact`→joinable `inference_registry.csv` (point estimate inline), `manifest.json`, `pch experiment status`; `docs/RUNNING_INFERENCE.md`.
- [ ] **M2** — Atomic `score`/`summarize` object API (`ScoreResult`); FN/FP in the registry. (`query`/`get` deferred — CSV is directly joinable.)
- [ ] **M3** — GA + ASTRAL3 runners (order-dependent).
- [ ] **M4** — wASTRAL + TREE-QMC runners (binary-interface discovery).
- [ ] **M5** — Pipeline executor + SLURM, concurrency-safe reruns (replace `run_parallel_sim.sh`).

**Docs are a per-milestone deliverable** — each milestone updates `docs/RUNNING_INFERENCE.md` (the human+agent run manual) and the `CLAUDE.md` docs index for what it shipped.

## Followups (from PR #18 review)

- [ ] Model `consensus_method` as a StrEnum (left as a plain string for now, per review).
- [ ] Tiny end-to-end integration test (run every method through `pch experiment inference` vs a reference; cache binary install; compare FN/FP + registry shape). Surfaced earlier; would catch the bugs live-testing found.
- [ ] Reconcile downstream stack (#19–#22) with the M1 changes (rebase) when ready.

## Done

- [x] Document inference methods in `docs/KEYS.md`.
- [x] Catalogue legacy bash scripts in `docs/HOW_TO_RUN.md`.
- [x] Add `docs/` index to `CLAUDE.md`.

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
