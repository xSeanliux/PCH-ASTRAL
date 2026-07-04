# CLI Operations

The config-driven CLI. Two layers: **atomic** commands (one dataset, one op) and **pipeline** commands (whole experiment from a YAML).

## Install

```bash
make setup          # install uv + `uv sync` (installs deps and the `pch` entry point)
make install-bins   # external binaries into bin/ (PAUP, MrBayes, ASTER, TREE-QMC)
uv run pch --help   # or: python3 -m scripts.py.cli.main --help
```
`pch` is the console script (`pyproject.toml [project.scripts]`); run it via `uv run pch …` (or activate the venv).

## Atomic commands (path-based; work on simulated or real data)

### `pch infer`
Run one inference method on one dataset CSV; returns the result.

```bash
pch infer DATASET.csv OUTPUT_DIR --method mp [--method-config cfg.yaml] [--json]
```
- `--method` — required; one of `mp`, `ga`, `pch_astral3`, `pch_wastral`, `pch_w_tree_qmc`.
- `--method-config` — YAML validated against the method's Pydantic model (required for methods with no all-default config, e.g. `pch_astral3`). No per-method flags.
- output: the tree(s) under `OUTPUT_DIR`; the `InferenceResult` is printed (human) or `--json` (one plain JSON line — pipe it, e.g. `pch infer d.csv out --method mp --json | jq` or `| bat`).

## Pipeline commands (`pch experiment …`, read the experiment YAML)

### `pch experiment inference EXPERIMENT.yaml`
Reads `{experiment_folder}/simulation_data/simulated_data_registry.csv`, runs the methods enabled under `methods:` for every dataset, and writes the joinable `inference_data/inference_registry.csv` (+ `manifest.json`).

### `pch experiment status EXPERIMENT_FOLDER`
Summarize the registry: total runs and counts per method.

### `pch experiment compact EXPERIMENT_FOLDER`
Merge the per-job shards into `inference_registry.csv` (normally automatic at the end of `inference`; run manually after a SLURM batch).

### `pch simulation EXPERIMENT.yaml`
Generate the simulated datasets (see `experiments/README.md`).

## Artifact model (`experiment_folder/inference_data/`)

- **`inference_registry.csv`** — one row per **successful** `(dataset, method, config)` run (the ledger is success-only; failed/blocked runs are logged, not rows). Columns = the simulation join keys (`poly_level, character_count, min_tree_height, homoplasy_factor, horizontal_edges, model_tree, replica`) + `method, config_hash, method_config_json, runtime_seconds, point_estimate_newick, tree_set_path, consensus_method, fn_rate, fp_rate, status, ran_at, log_path`. `status` is always `ok` (the scheduler skips already-recorded runs and gates dependents on these rows); `ran_at` is ISO8601 UTC. Joins to `simulated_data_registry.csv` on the shared keys. Schema: `scripts/py/cli/schemata.py`.
- **`shards/{job}.jsonl`** — transient per-job staging (one writer per SLURM job → lock-free); merged and removed by `compact`.
- **`manifest.json`** — run context (`created_at`, `completed_at`, methods, counts).

## End-to-end

```bash
pch simulation experiments/my_run/experiment_specification.yaml      # 1. simulate datasets
pch experiment inference experiments/my_run/experiment_specification.yaml   # 2. run inference -> registry
pch experiment status experiments/my_run                              # 3. check
```
Analyze by joining the two registries:
```python
import polars as pl
sim = pl.read_csv("experiments/my_run/simulation_data/simulated_data_registry.csv")
inf = pl.read_csv("experiments/my_run/inference_data/inference_registry.csv")
inf.join(sim, on=["poly_level","character_count","min_tree_height","homoplasy_factor","horizontal_edges","model_tree","replica"])
```
