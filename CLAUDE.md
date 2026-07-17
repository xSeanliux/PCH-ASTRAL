# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Docs

Check `docs/` first for anything not covered here:
- `docs/RUNNING_INFERENCE.md` — how to run the pipeline end to end (simulate → infer → analyze), reruns/failures, invariants. Start here to *run* it.
- `docs/ARCHITECTURE.md` — inference pipeline map: runner package, api/config/registry layers, the dependency mechanism, data flow, invariants. Read this first to orient.
- `docs/KEYS.md` — dataset/sim/inference join keys and what each inference method does.
- `docs/HOW_TO_RUN.md` — legacy bash inference scripts: I/O, key lines, caveats (migration reference).
- `docs/SCRIPT_CONTRACTS.md` — I/O contracts for the primitives the inference API shells out to.
- `docs/CLI.md` — the config-driven `simulation`/`inference` CLI.
- `docs/OPERATIONAL_ISSUES.md` — cluster-scale runbook: R-version ABI breaks, GA/4h-cap limits, ASTRAL heap, maintenance reservations, resume.

## What this is

PCH-ASTRAL infers linguistic phylogenies from polymorphic character matrices. The pipeline is **order-dependent**:
1. Run **MP4** and **GA** to produce candidate trees.
2. Generate quartet trees from the polymorphic data (`scripts/lib/pch.py`).
3. Run **ASTRAL** on those quartets, augmented by the MP4/GA bipartitions.

ASTRAL (heuristic mode) requires MP4 and GA bipartitions — always run those first.

## Commands

Python 3.12, managed with **uv**. See `Makefile` for all targets:

```bash
make setup            # install uv + uv sync
make install-bins     # install external binaries into bin/
make py-test          # pytest tests/
make py-static        # ty type-check
make py-fmt           # ruff format
make py-lint          # ruff check --fix
```

Run a single test: `uv run python -m pytest tests/scripts/lib/test_pch.py::<name>`

External deps not handled by `make`: **Java**, **R**, and `git submodule update --init` (ASTRAL jar). Binaries live in `bin/` (git-ignored).

Beware: `ASTRAL/` is the git submodule; `Astral/` is a separate top-level dir holding `astral.5.7.8.jar`. `scripts/sh/runASTRAL.sh` uses `ASTRAL/Astral/astral.5.7.8.jar` (relies on macOS case-insensitive FS).

## Two experiment systems (mid-migration)

1. **Legacy bash** — `run_inference_sim.sh` / `run_parallel_sim.sh` / `run_specific_dataset.sh` at repo root, backed by `scripts/sh/run{ASTRAL,GA,MP4}.sh`. Flag reference: `REPRODUCIBILITY.md`. Adding a new model condition requires updating hardcoded arrays near the top of `run_inference_sim.sh`. Outputs go to `sim_outputs/{MODEL_CONDITION}/{METHOD}/`.

2. **New config-driven CLI** — `scripts/py/cli/main.py` (Typer). Only `simulation` is implemented; `inference` is a stub. Spec format: `experiments/sample_experiment/experiment_specification.yaml` and `experiments/README.md`.
   ```bash
   python3 -m scripts.py.cli.main simulation experiments/sample_experiment/experiment_specification.yaml
   ```

## Key files in `scripts/`

- `lib/pch.py` — quartet generation (`PCH_W`, `PCH_O`); the core algorithm. Older docs may reference `lib/getQuartets.py` (renamed).
- `lib/types.py` — `Dataset`, `Quartet`, `Character`, `Polymorphism`. Dataset CSV format: first 3 cols `id,feature,weight`; remaining cols are taxa with `/`-separated polymorphic states.
- `lib/experiment.py` — Pydantic models for the YAML spec.
- `lib/simulation/types.py` — `SimulationConfigFactory` (scales base configs by character count / tree height).
- `R/` — NEXUS generation (`commandLineNex.R`), scoring (`RFScorer.R`), consensus trees (`consensusTree.R`).

## Data conventions

See `data/README.md`. Networks: `net{reticulation_edges}-{tree_num}.txt`; `A=0` is a plain tree. Simulation seeds are deterministic (hashed from registry key in `scripts/py/cli/handle_simulation.py`).

Type checker: **ty**. Linter: **ruff** (`E741` ignored, see `pyproject.toml`). Tests mirror `scripts/` under `tests/`.

## Brevity note 

Keep _all_ communication: be it code, docs, comments, or just agent interactions, brief. Aim to condense all writing such that if you remove any word it will take away from the idea of the sentence. Make sure sentences are brief, concise, easy to understand.
