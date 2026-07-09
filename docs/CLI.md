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

### `pch score`
RF-score one estimate tree against a reference Newick; prints `FN <fn> FP <fp>`.

```bash
pch score --estimate EST.tree --reference REF.tree [--json]
```
- `--json` → one plain JSON line (`{"fn_rate": …, "fp_rate": …}`) — pipeable.

### `pch summarize`
Consensus-collapse a tree set to a single Newick.

```bash
pch summarize --trees SET.trees --output OUT.tree --consensus {passthrough|majority|map|mcc} [--discard N]
```
- `--discard N` — drop the first `N` trees as burn-in (default 0).

## Pipeline commands (`pch experiment …`, read the experiment YAML)

> **Arg convention (uniform):** every `experiment` subcommand takes the spec **YAML** — the experiment folder is derived from it (`experiment_folder:`). Keep the spec inside the experiment folder.

### `pch experiment inference EXPERIMENT.yaml`
Reads `{experiment_folder}/simulation_data/simulated_data_registry.csv`, runs the methods enabled under `methods:` for every dataset, and writes the joinable `inference_data/inference_registry.csv` (+ `manifest.json`).

```bash
pch experiment inference EXPERIMENT.yaml [--executor local|slurm] [--datasets FILE] [--method M] \
    [--dry-run] [--resubmits K] [--astral-mem-gb N]
```
- `--executor local` (default) — run every enabled method in-process (today's behavior).
- `--datasets FILE` — text file of dataset paths (one per line); restrict the run to those datasets (matched by canonical path). Default = all sim rows.
- `--method M` — restrict a *local* run to one enabled method.

#### SLURM fan-out (`--executor slurm`)
Fans the work out as **one submitit job per (condition, method)** (condition = the dataset's parent-dir name, as in `run_parallel_sim.sh`). Method dependencies become `afterok` edges within a condition (MP4/GA → ASTRAL3); a final **compact** job depends `afterany` on all method jobs and merges the shards into the registry + manifest. Batch jobs write only per-job JSONL shards; only the compact job compacts — so concurrent jobs never race the manifest.
- **Requeue-on-timeout** absorbs the `secondary` queue's 4 h cap (`slurm_max_num_timeout=--resubmits`, default 3): a timed-out job auto-requeues, and idempotent `completed_runs` makes the rerun safe (finished datasets are skipped).
- **Two resource tiers**, not a per-method map: ASTRAL3 is `heavy` (big `mem_gb`/heap; override with `--astral-mem-gb N`), MP4/GA are `light`. Each job exports a short **node-local** scratch (`PCH_SCRATCH=/tmp/pch.$SLURM_JOB_ID`, dodging MrBayes' 99-char cap) and `PCH_ASTRAL_XMX` from its `mem_gb`.
- `--dry-run` prints the (condition, method) DAG + tiers + `afterok`/`afterany` edges and submits nothing (works without `sbatch`). Without `--dry-run`, a missing `sbatch` errors (no silent local fallback — use `--executor local` for that).

### `pch experiment score EXPERIMENT.yaml`
Join the inference registry to `simulated_data_registry.csv` (on `dataset_id`==`path`) to recover the model tree, RF-score each point estimate, and write `inference_data/scores.csv` (`dataset_id, method, config_hash, fn_rate, fp_rate`). Idempotent (rewrites).

### `pch experiment status EXPERIMENT.yaml`
Expected-vs-done gap view: per condition, `done/expected` for each enabled method (expected = sim datasets × methods; done = shard-aware `completed_runs`), plus the missing dataset stems. Reads registry ∪ uncompacted shards, so it's accurate mid-batch.

### `pch experiment compact EXPERIMENT.yaml`
Merge the per-job shards into `inference_registry.csv` (normally automatic at the end of a `local` run; run manually after a SLURM batch — though the fan-out's compact job usually handles it).

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
pch experiment status experiments/my_run/experiment_specification.yaml      # 4. check
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

## Environment & tuning

| Var | Default | Notes |
|-----|---------|-------|
| `R_LIBS` | (system) | R package library for scoring/consensus/nexus-gen. Must contain `shiny, optparse, dplyr, stringr, ape, testit, phangorn, castor, TreeDist`. Missing → `commandLineNex.R` halts and MP4/GA silently emit no tree. |
| `MB_EXEC` | `bin/mb` | MrBayes binary for GA. `make install-mrbayes` puts it at `bin/mb`; only override to use an mb elsewhere (e.g. a conda env). |
| `PCH_SCRATCH` | `$HOME/scratch` | Per-run temp (nexus, quartets, bipartitions). **Keep it short** — MrBayes 3.2.7a caps input filenames at 99 chars, so a deep scratch path silently fails GA (`Error when setting parameter "Filename" (2)`). |
| `PCH_ASTRAL_XMX` | `8g` | ASTRAL JVM heap. Bump for large inputs (e.g. `12g`, `64g`). |

**Scale note (ASTRAL memory):** the quartet file ASTRAL consumes has ≈ `n_chars × character_weight` weighted quartets (each character's quartets are emitted `weight` times as gene trees). High `n_chars` explodes this — 320 chars (weight ≈50) → ~410k quartets → OOMs the 8g default. Mitigate with `PCH_ASTRAL_XMX≥12g` or fewer characters.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| MP4/GA: `[failed] … (no tree)`; log shows `there is no package called '…'` | `R_LIBS` missing R deps → `commandLineNex.R` halts → empty NEXUS → PAUP/MrBayes produce nothing | Point `R_LIBS` at a library with the packages (see *Environment & tuning*). |
| ASTRAL3: `NoClassDefFoundError: phylonet/tree/io/ParseException` | `bin/Astral/` has the jar but no sibling `lib/` (jar manifest `Class-Path` is `lib/*.jar`) | `make install-astral3` (extracts jar + `lib/` into `bin/Astral/`). |
| Simulation: `Could not find or load main class Simulator` | `bin/LingPhyloSimulator.jar` built from LFS-pointer deps (git-lfs not pulled) | `git lfs pull`, then `make install-lingphylosimulator`. |
| `ModuleNotFoundError: No module named 'scripts.py.cli'` (via `uv run pch`) | `PYTHONPATH` includes another project with its own `scripts/` package, shadowing this repo | Clear `PYTHONPATH`, or run `python -m scripts.py.cli.main`. |
| GA: `Error when setting parameter "Filename" (2)`, no `GA/trees1/*.trees` | `PCH_SCRATCH` path > 99 chars (MrBayes cap) | Use a short `PCH_SCRATCH` (default `$HOME/scratch`). |
| ASTRAL: `OutOfMemoryError: Java heap space` | Too many weighted quartets for the heap | `PCH_ASTRAL_XMX=12g` (or higher), or fewer `n_chars`. |
| ASTRAL: `RuntimeException: Extra tree shouldn't have polytomy` | Unresolved MP4/GA tree fed to ASTRAL `-f` | Fixed in `getResultBipartitions` (`utils.resolve_polytomies`); update if you see it again. |
| `--executor slurm` errors on missing `sbatch` | No SLURM on this host | Use `--dry-run` to preview the plan, or `--executor local` to run in-process. |
