# Running Inference

The front door for *running* the config-driven inference pipeline. Task-oriented for humans; a precise contract for agents. Links the reference docs — it does not repeat them.

- Command/flag reference → `CLI.md`
- Internals (layers, runners, dependency mechanism) → `ARCHITECTURE.md`
- Join keys + what each method does → `KEYS.md`
- Shell primitive I/O contracts → `SCRIPT_CONTRACTS.md`

## Setup

```bash
make setup          # uv + `uv sync` (installs deps and the `pch` entry point)
make install-bins   # PAUP, MrBayes, ASTER, TREE-QMC into bin/
git submodule update --init   # ASTRAL jar
```
External deps `make` won't install: **Java** (ASTRAL), **R** (nexus-gen, scoring, consensus). Run `pch` via `uv run pch …` or activate the venv.

## Run an experiment end to end

```bash
YAML=experiments/my_run/experiment_specification.yaml
uv run pch simulation "$YAML"              # 1. simulate datasets -> simulation_data/
uv run pch experiment inference "$YAML"    # 2. run inference     -> inference_data/inference_registry.csv
uv run pch experiment status experiments/my_run   # 3. counts by method
```

Step 2 runs every method enabled under the YAML's `methods:` block for every dataset in the sim registry, scores each point estimate (FN/FP) against the model tree, and writes the joinable registry. Methods run in dependency order automatically (MP4/GA before ASTRAL3).

### Analyze — join the two registries

The registry is a plain CSV; analysis is a join, no bespoke query command.

```python
import polars as pl
sim = pl.read_csv("experiments/my_run/simulation_data/simulated_data_registry.csv")
inf = pl.read_csv("experiments/my_run/inference_data/inference_registry.csv")
inf.join(sim, on=["poly_level","character_count","min_tree_height",
                  "homoplasy_factor","horizontal_edges","model_tree","replica"])
```

## experiment_folder layout

```
experiments/my_run/
  experiment_specification.yaml       # config — source of truth
  simulation_data/  simulated_data_registry.csv, model trees, configs
  inference_data/
    inference_registry.csv            # THE joinable index (one row per dataset×method)
    shards/{job}.jsonl                # transient per-job staging; removed by compact
    manifest.json                     # created_at, completed_at, methods, n_runs
```
Everything lives under `experiment_folder/` — self-contained and portable. The point estimate is stored **inline** in the CSV (`point_estimate_newick`), not as a per-run file.

## Reading the registry

One row per `(dataset, method, config)`. Columns: the seven sim join keys + `method, config_hash, method_config_json, runtime_seconds, point_estimate_newick, tree_set_path, consensus_method, fn_rate, fp_rate, status, ran_at, log_path`. Schema: `scripts/py/cli/schemata.py`.

- `status` is `ok` or `failed`. A run is **`ok` only if** the command exited 0 **and** the point-estimate file was produced; otherwise `failed` with the reason in `log_path`.
- `config_hash` is part of the row identity, so the same dataset+method under two configs are distinct rows — they don't overwrite each other.

## Reruns, failures, resuming

Jobs time out and rerun (SLURM 4h cap), often in parallel. The design absorbs this:

- Each job appends to its **own** shard (`shards/{job}.jsonl`) — one writer per shard, no locks.
- `compact` merges shards → `inference_registry.csv`, **last-writer-wins by `ran_at`**, seeds from the existing registry, then deletes shards. `pch experiment inference` compacts at the end; after a bare SLURM batch, run it yourself:

```bash
uv run pch experiment compact experiments/my_run
```

Rerunning is safe and idempotent: a fresh run of the same `(dataset, method, config)` produces a newer `ran_at` and replaces the old row on compact. To find what's left, use `pch experiment status`.

## Real (non-simulated) datasets

`pch infer` runs one method on any CSV, simulated or not:

```bash
uv run pch infer DATASET.csv OUT_DIR --method mp [--method-config cfg.yaml] [--json]
```
It returns/prints the `InferenceResult`; the sim join keys are left `None`. There is **no registry** for atomic runs — the registry machinery is pipeline-only. Scoring real data needs a user-supplied reference (`pch score --estimate … --reference …`), not the model registry.

`--method-config` is a YAML validated against the method's Pydantic model, required for methods with a non-default config (e.g. `pch_astral3` needs `is_exact`). No per-method flags — the same YAML works for atomic and pipeline runs.

## Invariants (agents: respect these)

- **The Python API returns objects; everything renders them.** `api.infer → InferenceResult`, `score → ScoreResult`. The CLI and the registry CSV are renderings. The pipeline calls the API in-process and **never parses CLI stdout**.
- **`api.infer` never raises** — failures (nonzero exit, missing estimate, unmet prereqs) become `status=failed` rows via `failed_result` (real `config_hash`, so reruns dedup).
- **Order dependency:** heuristic ASTRAL3 needs MP4/GA bipartitions first. Runners declare this via `dependencies()`; the pipeline topo-sorts. Don't hand-order methods.
- **Writes are shard-per-job then compact.** Never write `inference_registry.csv` directly from a run; append a shard and let `compact` merge.
- **Config flows through the Pydantic model only** — never redefine a method's params outside its config class.

## Adding a method

See `ARCHITECTURE.md` § *Adding a method* (enum → config → runner → pipeline field → contract/tests).
