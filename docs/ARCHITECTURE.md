# Inference Architecture

Map of the config-driven inference pipeline (`scripts/lib/inference/` + `scripts/py/cli/`). For join keys see `KEYS.md`; for the shell primitives' I/O see `SCRIPT_CONTRACTS.md`; for CLI usage see `CLI.md`.

## Layers (bottom-up)

| Layer | Where | Responsibility |
|-------|-------|----------------|
| **Runners** | `lib/inference/runners/` | Per-method command + artifact-path construction. One file per runner. |
| **API** | `lib/inference/api.py` | `infer()` — the *only* subprocess site; always returns an `InferenceResult`. |
| **Config** | `lib/inference/method_config.py` | `MethodConfigT` union, `resolve_config`, `config_hash` (sha256). |
| **Types** | `lib/inference/inference.py` | `InferenceResult`, `RegistryRow`, and the `StrEnum`s. |
| **Registry** | `lib/inference/registry.py` | Shard-per-job JSONL → `compact` → joinable `inference_registry.csv`. |
| **Scoring** | `lib/inference/scoring.py`, `summarize.py` | RF FN/FP scoring; consensus summarization (shell out to R). |
| **Scheduler** | `lib/inference/scheduler.py` | Dependency order (topo) + the registry-backed ledger (skip/gate). |
| **Executor** | `lib/inference/executor.py` | `SlurmExecutor`: fans out one submitit job per (condition, method); method deps → `afterok` edges; final `afterany` compact job; requeue-on-timeout (`slurm_max_num_timeout`) absorbs the 4 h `secondary` cap; shard-aware `completed_runs` makes reruns idempotent; 2 resource tiers (heavy ASTRAL3 / light MP4+GA); node-local `PCH_SCRATCH`. See `specs/cli_specs/slurm_fanout_spec.md`. |
| **Pipeline** | `py/cli/handle_inference.py` | Orchestrates sim-registry → schedule → `api.infer` → registry; dispatches to `SlurmExecutor` when `--executor slurm`. |
| **Scoring step** | `py/cli/handle_score.py` | `pch experiment score`: join registry→sim, RF-score → `scores.csv`. |
| **CLI** | `py/cli/main.py` | `pch infer / score / summarize / experiment {inference,score,status,compact}`. |

## Runners (`runners/` package)

- `base.py` — the abstract layer: `Runner` (Protocol) + `_BaseRunner` (shared defaults).
- `mp4.py` / `ga.py` / `astral3.py` — one runner each (`MP4Runner`, `GARunner`, `ASTRAL3Runner`).
- `__init__.py` — the `RUNNERS: dict[TreeInferenceMethod, Runner]` registry + public re-exports. **Import surface:** `from scripts.lib.inference.runners import RUNNERS` (etc). `_BaseRunner.missing_prerequisites` uses a function-local `import RUNNERS` to avoid the `__init__ ↔ base` cycle.

Each runner is stateless (`@staticmethod` methods; the registry holds a singleton). A runner provides: `build_argv(runid, input_csv, name, output_dir, config)`, `point_estimate_path`, `group_estimate_path` (the tree *set*, or `None`), `consensus_method() -> Optional[ConsensusMethod]`, `log_path`, and `dependencies(config) -> [TreeInferenceMethod]` (upstreams whose output it consumes; ASTRAL3 → MP/GA from its `bipartition_strategies`, `[]` when exact).

## Scheduling (`scheduler.py`)

The registry holds **only successful results**, so a row for `(dataset, method)` means that method produced usable output for that dataset. The scheduler builds on that ledger:

1. **Enabled** = a config of the method's type (`METHOD_CONFIG[method]`) is present in `MethodConfig` (matched by class, no field-name table).
2. **Order** — `topological_order` puts each method after the enabled deps it needs (deps enabled elsewhere / run separately are ignored here; the gate covers them). Cycles raise.
3. Per `(dataset, method)`, `completed_runs` (the prior registry as `{dataset → {(method, config_hash)}}`, plus this run's successes) decides:
   - **skip** if `(dataset, method, config_hash)` is already recorded — *resume*, don't redo work;
   - **block** (log, no row) if a dependency has no successful result — counting this run **and** prior runs;
   - else **run** `api.infer`; **OK → a registry row**, **failed → log only**.

So MP4/GA/ASTRAL3 work whether run together or as separate ordered invocations, and re-running an experiment only fills the gaps. A missing upstream is a *block* (never ran), distinct from a *failure* (ran, errored) — both stay out of the registry. With `--executor slurm`, `SlurmExecutor` translates `dependencies()` into submitit `afterok` edges between per-(condition, method) jobs (see `specs/cli_specs/slurm_fanout_spec.md`).

## Data flow (`pch experiment inference`)

```
simulation_data/simulated_data_registry.csv
  └─ for each row (dataset) × each enabled method (topological order):
       already recorded (same config)?           → skip
       a dependency has no success (this run/prior)? → block (log)
       else api.infer(csv, out_dir, method, config)
         → subprocess(runner.build_argv) → InferenceResult (dataset_id = input path)
         → OK  → registry.write_result → inference_data/shards/{job}.jsonl
         → FAILED → log only (not in the registry)
  └─ registry.compact → inference_data/inference_registry.csv (+ manifest.json)
```

The registry is **generic** — keyed by `dataset_id` = the input CSV path, source-agnostic (a real CSV runs identically). Sim metadata and FN/FP are decoupled:
- **sim keys** = a join to `simulated_data_registry.csv` on `dataset_id`==`path`.
- **FN/FP** = `pch experiment score` (`handle_score.py`), a separate step that recovers `model_tree` via that join, resolves the base tree, RF-scores each point estimate, and writes `scores.csv` (`dataset_id, method, config_hash, fn_rate, fp_rate`).

Analysis = `inference_registry.csv` ⨝ `simulated_data_registry.csv` (on `dataset_id`==`path`) ⨝ `scores.csv` (on `dataset_id, method, config_hash`). See `KEYS.md`.

## Key invariants

- **The registry is the ledger of *successful* results only** — blocks and failures are logged, never written. So a row = analyzable data, and *presence* of `(dataset, method, config_hash)` means "done" (drives both resume and the dependency gate).
- **`api.infer` always returns an `InferenceResult`** — a nonzero exit or a missing point estimate becomes `status=FAILED`, never an exception; the pipeline just doesn't record it.
- A run is **OK only if** it exited 0 **and** the point-estimate file exists.
- Registry dedup key (`run_key`) includes `config_hash`; `compact` is last-writer-wins (by `ran_at`), seeds from the existing registry, and deletes shards.
- **Order:** heuristic ASTRAL3 needs MP4 + GA bipartitions, so the scheduler topologically orders it after them (and gates on their success via the registry).

## Shell primitives

`api.infer` shells out to `scripts/sh/run{MP4,GA}.sh` and `scripts/sh/runASTRAL3.sh` (the CLI ASTRAL variant; legacy `runASTRAL.sh` kept for the old bash pipeline). Contracts in `SCRIPT_CONTRACTS.md`. Env: `$PCH_SCRATCH` (scratch dir), `$PCH_ASTRAL_XMX` (ASTRAL JVM heap, default `8g`). ASTRAL3 output folder name is single-sourced in Python (`ASTRAL3Runner.VARIANT`) and passed to the script via `-V`.

## Adding a method

1. Add the enum member to `TreeInferenceMethod` (`inference.py`) + its config to `MethodConfigT`/`METHOD_CONFIG` (`method_config.py`) and a field on `MethodConfig` (`experiment.py`).
2. Add `runners/<method>.py` implementing the `Runner` protocol (incl. `dependencies(config)` if it has upstreams); register it in `runners/__init__.py`.
3. Document its shell contract in `SCRIPT_CONTRACTS.md`; add tests mirroring `tests/scripts/lib/inference/`.

Enablement is by config type (`config_for`) and order is topological from `dependencies()`, so there's no field-name table or hand-ordering to update.
