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

Each runner is stateless (`@staticmethod` methods; the registry holds a singleton). A runner provides: `build_argv(runid, input_csv, name, output_dir, config)`, `point_estimate_path`, `group_estimate_path` (the tree *set*, or `None`), `consensus_method() -> Optional[ConsensusMethod]`, `log_path`, `dependencies(config)`, `missing_prerequisites(config, output_dir, name)`.

## Dependencies (generic, not method-specific)

Runners declare upstreams via `dependencies(config) -> list[TreeInferenceMethod]` (default `[]`; `ASTRAL3Runner` maps its `bipartition_strategies` → MP/GA, `[]` when exact). `handle_inference` is method-agnostic and uses this for:

1. **Co-requisite** — a selected method's deps must also be enabled, else a clear `ValueError`.
2. **Ordering** — topological sort so deps run before dependents (yields MP → GA → ASTRAL3).
3. **Gate (CLI / 2a)** — per row, if a dep's in-memory status ≠ OK → record `FAILED` (via `api.failed_result`), skip. `missing_prerequisites` (filesystem: does each dep's `group_estimate_path` exist) is the atomic-run backstop.
4. **SLURM (2b, future)** — `dependencies()` is the hook a job launcher would `--dependency`/await on. Not yet implemented.

## Data flow (`pch experiment inference`)

```
simulation_data/simulated_data_registry.csv
  └─ for each row (dataset) × each method (topo order):
       handle_inference → api.infer(csv, out_dir, method, config)
         → runner.missing_prerequisites? → failed_result   (never raises)
         → else subprocess(runner.build_argv) → InferenceResult
       → stamp sim join keys, RF-score point estimate (fn/fp)
       → registry.write_result → inference_data/shards/{job}.jsonl
  └─ registry.compact → inference_data/inference_registry.csv (+ manifest.json)
```

Analysis = join `inference_registry.csv` to `simulated_data_registry.csv` on the shared sim keys (see `KEYS.md`).

## Key invariants

- **`api.infer` always returns an `InferenceResult`** — failures (nonzero exit, missing point estimate, unmet prereqs) become `status=FAILED`, never an exception. `failed_result()` is the single shared FAILED-row builder (real `config_hash` so reruns dedup correctly).
- A run is **OK only if** it exited 0 **and** the point-estimate file exists.
- Registry dedup key (`run_key`) includes `config_hash`; `compact` is last-writer-wins (by `ran_at`), seeds from the existing registry, and deletes shards.
- **Order dependency:** heuristic ASTRAL3 needs MP4 + GA bipartitions first (see `dependencies`).

## Shell primitives

`api.infer` shells out to `scripts/sh/run{MP4,GA}.sh` and `scripts/sh/runASTRAL3.sh` (the CLI ASTRAL variant; legacy `runASTRAL.sh` kept for the old bash pipeline). Contracts in `SCRIPT_CONTRACTS.md`. Env: `$PCH_SCRATCH` (scratch dir), `$PCH_ASTRAL_XMX` (ASTRAL JVM heap, default `8g`). ASTRAL3 output folder name is single-sourced in Python (`ASTRAL3Runner.VARIANT`) and passed to the script via `-V`.

## Adding a method

1. Add the enum member to `TreeInferenceMethod` (`inference.py`) + its config to `MethodConfigT`/`METHOD_CONFIG` (`method_config.py`).
2. Add `runners/<method>.py` (subclass `_BaseRunner`); register it in `runners/__init__.py`.
3. If it has upstreams, implement `dependencies(config)` — ordering/co-requisite/gating come for free.
4. Add the `(method, config-attr)` pair to `_METHOD_FIELDS` in `handle_inference.py`.
5. Document its shell contract in `SCRIPT_CONTRACTS.md`; add tests mirroring `tests/scripts/lib/inference/`.
