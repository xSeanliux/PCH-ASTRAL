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

### `pch experiment score EXPERIMENT.yaml`
Join the inference registry to `simulated_data_registry.csv` (on `dataset_id`==`path`) to recover the model tree, RF-score each point estimate, and write `inference_data/scores.csv` (`dataset_id, method, config_hash, fn_rate, fp_rate`). Idempotent (rewrites).

### `pch experiment status EXPERIMENT_FOLDER`
Summarize the registry: total runs and counts per method.

### `pch experiment compact EXPERIMENT_FOLDER`
Merge the per-job shards into `inference_registry.csv` (normally automatic at the end of `inference`; run manually after a SLURM batch).

### `pch simulation EXPERIMENT.yaml`
Generate the simulated datasets (see `experiments/README.md`).

## Artifact model (`experiment_folder/inference_data/`)

- **`inference_registry.csv`** — one row per **successful** `(dataset, method, config)` run, **generic** (source-agnostic; the ledger is success-only, failed/blocked runs are logged, not rows). Columns = `dataset_id` (the input CSV path — the identity), `method, config_hash, method_config_json, runtime_seconds, point_estimate_newick, tree_set_path, consensus_method, status, ran_at, log_path`. No sim keys and no FN/FP — those are a join (`simulated_data_registry.csv` on `dataset_id`==`path`) and a separate table (`scores.csv`, from `pch experiment score`). `status` is always `ok` (the scheduler skips already-recorded runs and gates dependents on these rows); `ran_at` is ISO8601 UTC. Schema: `scripts/py/cli/schemata.py`.
- **`scores.csv`** — FN/FP per `(dataset_id, method, config_hash)`, written by `pch experiment score`. Join to `inference_registry.csv` on those three columns.
- **`shards/{job}.jsonl`** — transient per-job staging (one writer per SLURM job → lock-free); merged and removed by `compact`.
- **`manifest.json`** — run context (`created_at` [first run], `completed_at`, `methods`, `tally` = ok/skipped/blocked/failed).

## End-to-end

```bash
pch simulation experiments/my_run/experiment_specification.yaml      # 1. simulate datasets
pch experiment inference experiments/my_run/experiment_specification.yaml   # 2. run inference -> registry
pch experiment score experiments/my_run/experiment_specification.yaml       # 3. FN/FP -> scores.csv
pch experiment status experiments/my_run                              # 4. check
```
Analyze by joining the three tables on `dataset_id`:
```python
import polars as pl
sim = pl.read_csv("experiments/my_run/simulation_data/simulated_data_registry.csv")
inf = pl.read_csv("experiments/my_run/inference_data/inference_registry.csv")
scores = pl.read_csv("experiments/my_run/inference_data/scores.csv")
(inf.join(sim, left_on="dataset_id", right_on="path")
    .join(scores, on=["dataset_id", "method", "config_hash"]))
```
