# Tasks

Task tracking for PCH-ASTRAL. Other progress artifacts live alongside this file under `progress/`.

## In progress

- [ ] Migrate legacy bash inference to the config-driven CLI. **Plan:** [`progress/plans/2026-06-22-inference-cli-migration.md`](plans/2026-06-22-inference-cli-migration.md) (5 milestones; M1 = MP4 slice, fully task-decomposed). References: `docs/HOW_TO_RUN.md`, `specs/cli_specs/human_specs.md`.

## To do

- [ ] **M1** — MP4 inference slice + scaffolding (fixes the `inference.py` mutable-default crash; wires the `inference` CLI command). See plan.
- [ ] **M2** — GA + ASTRAL3 runners; reconcile `runASTRAL.sh`'s stale `printQuartets.py -q` call with the current `-i`/`-w` interface.
- [ ] **M3** — FN/FP scoring & runtime metrics in the registry.
- [ ] **M4** — wASTRAL + TREE-QMC runners (binary-interface discovery).
- [ ] **M5** — SLURM orchestration (replace `run_parallel_sim.sh`).

## Done

- [x] Document inference methods in `docs/KEYS.md`.
- [x] Catalogue legacy bash scripts in `docs/HOW_TO_RUN.md`.
- [x] Add `docs/` index to `CLAUDE.md`.
