# Tasks

Task tracking for PCH-ASTRAL.

## In progress

- [ ] Migrate legacy bash inference to the config-driven CLI. **Plan:** [`progress/plans/2026-06-22-inference-cli-migration.md`](plans/2026-06-22-inference-cli-migration.md) (5 milestones; M1 = MP4 slice, fully task-decomposed). References: `docs/HOW_TO_RUN.md`, `specs/cli_specs/human_specs.md`.

## To do

- [ ] **M0** — Script hardening & interface contracts + `docs/SCRIPT_CONTRACTS.md` (fix stale `printQuartets.py`, drop `~/scratch` hardcoding). See plan.
- [ ] **M1** — Three-layer scaffolding: Python API (`infer → InferenceResult`), `METHOD_CONFIG` registry, atomic `pch infer --method mp4`, pipeline slice. Artifact model: `.parts`→`compact`→joinable `inference_registry.csv` (point estimate inline), `manifest.json`, `pch experiment status`; `docs/RUNNING_INFERENCE.md`.
- [ ] **M2** — Atomic `score`/`summarize` object API (`ScoreResult`); FN/FP in the registry. (`query`/`get` deferred — CSV is directly joinable.)
- [ ] **M3** — GA + ASTRAL3 runners (order-dependent).
- [ ] **M4** — wASTRAL + TREE-QMC runners (binary-interface discovery).
- [ ] **M5** — Pipeline executor + SLURM, concurrency-safe reruns (replace `run_parallel_sim.sh`).

**Docs are a per-milestone deliverable** — each milestone updates `docs/RUNNING_INFERENCE.md` (the human+agent run manual) and the `CLAUDE.md` docs index for what it shipped.

## Done

- [x] Document inference methods in `docs/KEYS.md`.
- [x] Catalogue legacy bash scripts in `docs/HOW_TO_RUN.md`.
- [x] Add `docs/` index to `CLAUDE.md`.
