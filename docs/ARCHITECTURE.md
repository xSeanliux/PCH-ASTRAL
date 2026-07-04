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
| **Pipeline** | `py/cli/handle_inference.py` | Orchestrates sim-registry → `api.infer` per `(dataset, method)` → registry. |
| **CLI** | `py/cli/main.py` | `pch infer / score / summarize / experiment {inference,status,compact}`. |

## Runners (`runners/` package)

- `base.py` — the abstract layer: `Runner` (Protocol) + `_BaseRunner` (shared defaults).
- `mp4.py` / `ga.py` / `astral3.py` — one runner each (`MP4Runner`, `GARunner`, `ASTRAL3Runner`).
- `__init__.py` — the `RUNNERS: dict[TreeInferenceMethod, Runner]` registry + public re-exports. **Import surface:** `from scripts.lib.inference.runners import RUNNERS` (etc). `_BaseRunner.missing_prerequisites` uses a function-local `import RUNNERS` to avoid the `__init__ ↔ base` cycle.

Each runner is stateless (`@staticmethod` methods; the registry holds a singleton). A runner provides: `build_argv(runid, input_csv, name, output_dir, config)`, `point_estimate_path`, `group_estimate_path` (the tree *set*, or `None`), `consensus_method() -> Optional[ConsensusMethod]`, `log_path`.

## Method selection & order

`select_methods` returns the enabled methods — enabled = a config of the method's type (`METHOD_CONFIG[method]`) is present in the experiment's `MethodConfig` (matched by class, no field-name table). They run in **fixed `RUNNERS` order** (MP4 → GA → ASTRAL3), so a combined run produces ASTRAL3's bipartition inputs before ASTRAL3 runs.

There is deliberately **no dependency scheduler** here: running MP4/GA/ASTRAL3 as separate ordered invocations is valid (prior outputs live on disk), and a missing input just **fails that run** — heuristic ASTRAL3 without MP4/GA `.trees` makes `getResultBipartitions` exit nonzero → `api.infer` records `FAILED`. Cross-run dependency ordering / awaiting (SLURM `--dependency`) is a **separate future PR**.

## Data flow (`pch experiment inference`)

```
simulation_data/simulated_data_registry.csv
  └─ for each row (dataset) × each enabled method (fixed order):
       handle_inference → api.infer(csv, out_dir, method, config)
         → subprocess(runner.build_argv) → InferenceResult (FAILED if exit≠0
           or no point estimate — e.g. ASTRAL3 with missing inputs)
       → stamp sim join keys, RF-score point estimate (fn/fp)
       → registry.write_result → inference_data/shards/{job}.jsonl
  └─ registry.compact → inference_data/inference_registry.csv (+ manifest.json)
```

Analysis = join `inference_registry.csv` to `simulated_data_registry.csv` on the shared sim keys (see `KEYS.md`).

## Key invariants

- **`api.infer` always returns an `InferenceResult`** — a nonzero exit or a missing point estimate becomes `status=FAILED`, never an exception.
- A run is **OK only if** it exited 0 **and** the point-estimate file exists.
- Registry dedup key (`run_key`) includes `config_hash`; `compact` is last-writer-wins (by `ran_at`), seeds from the existing registry, and deletes shards.
- **Order:** heuristic ASTRAL3 needs MP4 + GA bipartitions, so it runs after them via the fixed `RUNNERS` order (not a scheduler).

## Shell primitives

`api.infer` shells out to `scripts/sh/run{MP4,GA}.sh` and `scripts/sh/runASTRAL3.sh` (the CLI ASTRAL variant; legacy `runASTRAL.sh` kept for the old bash pipeline). Contracts in `SCRIPT_CONTRACTS.md`. Env: `$PCH_SCRATCH` (scratch dir), `$PCH_ASTRAL_XMX` (ASTRAL JVM heap, default `8g`). ASTRAL3 output folder name is single-sourced in Python (`ASTRAL3Runner.VARIANT`) and passed to the script via `-V`.

## Adding a method

1. Add the enum member to `TreeInferenceMethod` (`inference.py`) + its config to `MethodConfigT`/`METHOD_CONFIG` (`method_config.py`) and a field on `MethodConfig` (`experiment.py`).
2. Add `runners/<method>.py` implementing the `Runner` protocol; register it in `runners/__init__.py` (its position sets run order).
3. Document its shell contract in `SCRIPT_CONTRACTS.md`; add tests mirroring `tests/scripts/lib/inference/`.

Enablement is by config type (`config_for`), so there's no field-name table to update.
