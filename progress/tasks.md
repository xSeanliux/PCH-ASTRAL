# Tasks

Task tracking for PCH-ASTRAL.

## In progress

- [ ] Migrate legacy bash inference to the config-driven CLI. **Plan:** [`progress/plans/2026-06-22-inference-cli-migration.md`](plans/2026-06-22-inference-cli-migration.md) · **Agent-team split + gap review:** [`…-agent-team.md`](plans/2026-06-22-inference-cli-agent-team.md). References: `docs/HOW_TO_RUN.md`, `specs/cli_specs/human_specs.md`.

## In review (stacked PRs, each on the previous)

- [x] **M0** — Script hardening + `docs/SCRIPT_CONTRACTS.md` — PR #17
- [x] **M1** — Three-layer scaffolding + MP4 + artifact model (`.parts`→`compact`, joinable registry, manifest, `pch experiment status`) — PR #18
- [x] **M2** — `score`/`summarize` object API; FN/FP in registry (base-tree reference) — PR #19
- [x] **M3** — GA + ASTRAL3 runners + order-dependency + per-method pipeline config — PR #20
- [x] **M4** — wASTRAL + TREE-QMC runners; `install_aster` builds from source; verified tree-qmc + wASTRAL (`--mode 4`) end-to-end — PR #21

## To do

- [ ] **M5** — Pipeline executor + SLURM (`submitit`), concurrency-safe reruns (replace `run_parallel_sim.sh`). See plan.
- [ ] **Tiny end-to-end integration test** — run *every* method (MP4, GA, ASTRAL3, wASTRAL, TREE-QMC) through `pch experiment inference` on a minimal dataset and compare to a checked-in reference. Design notes:
  - **Cache the binary install** — building ASTER/TREE-QMC + downloading PAUP/MrBayes is slow; key a CI cache on the `install_*.sh` hashes (or a session-scoped fixture that installs once). `skipif` when a binary is absent.
  - **Tiny + deterministic** — a few taxa / few characters; seed where supported (MrBayes seed for GA, tree-qmc `--seed`, etc.). Note GA (MCMC) and max-cut have inherent randomness.
  - **Compare robustly, not byte-exact** — methods are nondeterministic, so don't diff Newick. Assert FN/FP against the known true tree within a tolerance, plus registry shape (one row per `(dataset, method)`, expected columns populated). The "reference" is acceptable FN/FP bounds + the expected registry schema, not a golden tree string.
  - Surfaced by M4 live-testing: such a test would have caught the float-weight crash, the `paste -d''` format bug, the `MB_EXEC` path, and the wASTRAL `--mode 4` weighting — all of which mocks missed.

**Docs are a per-milestone deliverable** — each milestone updates `docs/RUNNING_INFERENCE.md` (the human+agent run manual) and the `CLAUDE.md` docs index for what it shipped.

## Done

- [x] Document inference methods in `docs/KEYS.md`.
- [x] Catalogue legacy bash scripts in `docs/HOW_TO_RUN.md`.
- [x] Add `docs/` index to `CLAUDE.md`.
