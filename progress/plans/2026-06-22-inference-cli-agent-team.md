# Inference CLI Migration — Agent-Team Delegation

Companion to `2026-06-22-inference-cli-migration.md`. How to split that plan across an agent team: the roster, and per-milestone a concrete delegatable task list (with owner, dependencies, and parallel wave). Read the plan first — this only assigns its work.

## Operating model

- **One lead (you) + specialists.** The lead sequences waves, reviews each task's diff, runs the gate, and integrates. Specialists own files, not features — so two agents rarely touch the same file in one wave (the main source of merge pain).
- **TDD per task** (the plan's tasks already specify the test). Each specialist writes the failing test, implements, makes it green. The **Tests agent** owns only the cross-cutting/riskiest suites (compact concurrency) and the CI gate.
- **Gate between waves:** `uv run python -m pytest tests/ -q && make py-static && make py-fmt`. Nothing merges red.
- **Parallelism = a wave.** Tasks in the same wave touch disjoint files and can run as concurrent subagents; the next wave starts after the gate passes.

## Roster

| Agent | Owns | Skills | Heaviest in |
|-------|------|--------|-------------|
| **Scripts & Contracts** | `scripts/sh/`, `scripts/R/`, binary interfaces, `docs/SCRIPT_CONTRACTS.md` | bash, R, the external tools | M0, M4 |
| **Core/Lib** | `scripts/lib/inference/` (inference, methods, runners, registry, api, scoring, executor) | Python, Pydantic, Polars | M1, M2, M5 |
| **CLI & Pipeline** | `scripts/py/cli/` (main, handle_inference, schemata) | Typer, orchestration | M1, M3, M5 |
| **Tests & Types** | smoke harness, compact concurrency/idempotency suite, ty/ruff gate | pytest, ty | every milestone |
| **Docs** | `RUNNING_INFERENCE.md`, `SCRIPT_CONTRACTS.md`, `docs/CLI.md`, `CLAUDE.md` index | technical writing | every milestone |

Lean on purpose — Core/Lib + CLI are the two doers; Scripts/Tests/Docs are specialists pulled in where the milestone needs them. Scale Core/Lib to 2–3 parallel subagents within a wave when tasks are disjoint.

---

## M0 — Script hardening & contracts

| ID | Task | Owner | Depends | Wave |
|----|------|-------|---------|------|
| 0.1 | `docs/SCRIPT_CONTRACTS.md` skeleton — one row per primitive (command, I/O, stdout/stderr shape, exit codes) | Docs + Scripts | — | A |
| 0.2 | MP4 primitive — decide keep-`.sh` vs inline; `PCH_SCRATCH` env (drop hardcoded `~/scratch`); enforce contract + exit codes | Scripts | 0.1 | B |
| 0.3 | GA + ASTRAL primitives — same; **fix stale `printQuartets.py -q`** (script passes `-q`, current py takes `-i`/`-w`) | Scripts | 0.1 | B |
| 0.4 | `RFScorer.R` — stdout exactly one line `fn fp`; diagnostics → stderr; exit codes | Scripts | 0.1 | B |
| 0.5 | `consensusTree.R` — contract + exit codes | Scripts | 0.1 | B |
| 0.6 | Smoke test per primitive, `@skipif(binary missing)` | Tests | 0.2–0.5 | C |

Wave B (0.2–0.5) is fully parallel — different files. Gate: contracts doc matches observed behavior.

## M1 — three-layer scaffolding (the big one)

| ID | Task | Owner | Depends | Wave |
|----|------|-------|---------|------|
| 1.1 | `TreeInferenceMethod` enum + `InferenceResult` (final shape) + `to_registry_row()` | Core | — | A |
| 1.3 | `runners.py` MP4 (argv + paths, the TDD exemplar) | Core | 1.1 enum | A |
| 1.4 | `methods.py` — `METHOD_CONFIG` + `resolve_config` + `config_hash` | Core | 1.1 enum | A |
| 1.2 | `INFERENCE_REGISTRY_SCHEMA` (final columns, == `to_registry_row` keys) | CLI | 1.1 | B |
| 1.5 | `registry.py` — `run_key`, atomic `.parts` write, **`compact`**, manifest | Core | 1.1, 1.2 | B |
| 1.6 | `api.infer() -> InferenceResult` (reads point estimate, sets status/ran_at; only `subprocess` site) | Core | 1.1, 1.3, 1.4 | B |
| 1.7 | `handle_inference` pipeline — loop registry → `api.infer` → `write_part` → `compact` + manifest | CLI | 1.5, 1.6, 1.2 | C |
| 1.8 | Wire `pch infer` / `experiment inference` / `status` / `compact` + `[project.scripts] pch` | CLI | 1.6, 1.7 | D |
| 1.T | **Compact concurrency/idempotency suite** — duplicate-`run_key` atomic write, last-writer-wins, rerun = no dup rows | Tests | 1.5 | C |

Wave A: split 1.1/1.3/1.4 across Core subagents — but land 1.1's *enum* first (a 5-min stub) since 1.3/1.4 import it. Docs updates `RUNNING_INFERENCE.md` after wave D. The compact suite (1.T) is where most test effort goes.

## M2 — score + summarize

| ID | Task | Owner | Depends | Wave |
|----|------|-------|---------|------|
| 2.1 | `scoring.py` — `ScoreResult` + `score()` wrapping `RFScorer.R` (parse one-line stdout) | Core | M0 0.4 | A |
| 2.2 | `summarize.py` wrapping `consensusTree.R` | Core | M0 0.5 | A |
| 2.3 | **Reference resolution** — base tree `(0, model_tree)` from `model_graph_registry.csv`, never the network (gap G7) | Core | — | A |
| 2.4 | Populate `fn_rate`/`fp_rate` — `handle_inference` calls `score()` in-process | CLI | 2.1, 2.3 | B |
| 2.5 | `pch score` / `pch summarize` CLI (text + `--json`) | CLI | 2.1, 2.2 | B |
| 2.6 | Tests + `RUNNING_INFERENCE.md` scoring section | Tests + Docs | 2.4 | C |

## M3 — GA + ASTRAL3

| ID | Task | Owner | Depends | Wave |
|----|------|-------|---------|------|
| 3.1 | GA runner (argv/paths over M0 GA primitive) | Core | M0 | A |
| 3.2 | ASTRAL3 runner + `ASTRAL3Config.bipartition_strategies` wiring | Core | M0 | A |
| 3.3 | **Prerequisite-exists check** in `infer(astral3)` + method ordering in `handle_inference` | Core + CLI | 3.1, 3.2 | B |
| 3.4 | Order-dependency tests + docs | Tests + Docs | 3.3 | C |

## M4 — wASTRAL + TREE-QMC

| ID | Task | Owner | Depends | Wave |
|----|------|-------|---------|------|
| 4.1 | **Discover + contract** the wASTRAL (ASTER) + TREE-QMC binary CLIs → `SCRIPT_CONTRACTS.md` (M0-style) | Scripts | — | A |
| 4.2 | wASTRAL runner + fill `WeightedASTRALConfig` | Core | 4.1 | B |
| 4.3 | TREE-QMC runner + `WeightedTreeQMCConfig.normalisation_strategy` | Core | 4.1 | B |
| 4.4 | PCH-W quartet wiring (`printQuartets.py -w`) | Core | 4.1 | B |
| 4.5 | Tests + docs | Tests + Docs | 4.2–4.4 | C |

4.1 gates everything — the binary interfaces are unknown, so it's a discovery task before any code.

## M5 — executor + SLURM

| ID | Task | Owner | Depends | Wave |
|----|------|-------|---------|------|
| 5.1 | `executor.py` — `LocalExecutor` (inline `api.infer`) | Core | — | A |
| 5.2 | `SlurmExecutor` via `submitit` (arrays, `afterok` deps, requeue-on-timeout) | Core | 5.1 | B |
| 5.3 | `--executor local\|slurm` + `--dry-run` wiring | CLI | 5.1 | B |
| 5.4 | Method-ordering → submitit dependency chains | Core | 5.2, M3 ordering | C |
| 5.5 | Dry-run test (assert submission spec, no live submit) + docs | Tests + Docs | 5.3 | C |

---

## Gap review (this pass)

| # | Gap | Severity | Resolution | Status |
|---|-----|----------|-----------|--------|
| G1 | `InferenceResult`/schema draft predates the artifact model (no `config_hash`, inline newick, status/ran_at) | High | Pinned *Final InferenceResult & registry columns*; Tasks 1–2 build to it | **Fixed in plan** (code regen at execution) |
| G2 | No owner for `config_hash` / `run_key` | Med | `config_hash` → `methods.py` (T1.4); `run_key` → `registry.py` (T1.5) | **Fixed** |
| G3 | No owner for `manifest.json` | Med | `registry.py` init/finalize; `handle_inference` calls (T1.7) | **Fixed** |
| G4 | `compact` (riskiest logic) had no explicit task | High | `registry.py` owns it (T1.5) + dedicated suite (T1.T) | **Fixed** |
| G5 | Real datasets have no simulation keys | Med | universal `dataset_id`; sim keys nullable; atomic `infer` writes no registry | **Fixed** |
| G6 | Experiment YAML expresses one config per method | Low | documented; `list`-configs deferred (YAGNI) | **Flagged — confirm OK** |
| G7 | Networks scored against the network, not a binary tree | **High (correctness)** | score against base tree `(0, model_tree)` | **Fixed (M2)** |
| G8 | Consensus logic in both `runMP4.sh` and M2 `summarize()` | Low | if M0 inlines MP4, reuse `summarize()`; alignment noted | Flagged |
| G9 | `pch` command not actually installed | Low | `[project.scripts] pch` in T1.8 | **Fixed** |
| G10 | `config_hash` must be stable across runs | Low | sha256 of `model_dump_json()` (stable field order) | **Fixed (T1.4)** |
| G11 | `compact` tie-break on equal `ran_at` | Low | last-writer-wins by `ran_at`, ties arbitrary-but-deterministic | Noted |

### Residual decisions for you
1. **G6** — one config per method per experiment is fine for now? (recommend yes; lists are easy to add later.)
2. **submitit** as a new dependency for M5 (recommend yes — it owns the SLURM array/dependency/requeue logic).
3. **M0 keep-`.sh`-vs-inline** is decided per primitive *during* M0 — not blocking, but the Scripts agent records each choice in `SCRIPT_CONTRACTS.md`.
