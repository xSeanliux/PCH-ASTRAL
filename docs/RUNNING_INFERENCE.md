# Running Inference

The front door for *running* the config-driven inference pipeline. Task-oriented for humans; a precise contract for agents. Links the reference docs — it does not repeat them.

- Command/flag reference → `CLI.md`
- Internals (layers, runners, dependency mechanism) → `ARCHITECTURE.md`
- Join keys + what each method does → `KEYS.md`
- Shell primitive I/O contracts → `SCRIPT_CONTRACTS.md`

## Setup

```bash
git lfs install && git lfs pull   # fetch bin/lingphylosimulator_jars/*.jar (LFS)
make setup          # uv + `uv sync` (installs deps and the `pch` entry point)
make install-bins   # PAUP, MrBayes, ASTER, TREE-QMC, ASTRAL, LingPhyloSimulator into bin/
```
External deps `make` won't install: **Java** (ASTRAL/simulator), **R** (nexus-gen, scoring, consensus). Run `pch` via `uv run pch …` or activate the venv.

**Prerequisites, in order (each blocks the pipeline if missing):**

1. **git-lfs.** `bin/lingphylosimulator_jars/*.jar` (the simulator's build deps) are LFS-tracked. Without `git lfs pull` they're 130-byte pointers, and `make install-lingphylosimulator` builds a broken `bin/LingPhyloSimulator.jar` (silent `javac` failure → `Could not find or load main class Simulator` when simulating). No git-lfs on the machine? Grab a static binary from the [git-lfs releases](https://github.com/git-lfs/git-lfs/releases) and put it on `PATH`.
2. **`make install-bins`** populates `bin/`: `bin/mb` (MrBayes → GA's default `MB_EXEC`), `bin/paup` (MP4), `bin/Astral/` (jar **and** its `lib/` — the jar's manifest `Class-Path` is `lib/*.jar`), `bin/LingPhyloSimulator.jar` (simulation), plus ASTER/TREE-QMC. Individual targets: `make install-mrbayes`, `install-paup`, `install-astral3`, `install-lingphylosimulator`. MrBayes builds from source — run it from a directory whose C compiler works (empty `LIBRARY_PATH`/`CPATH` entries can make `gcc` fail on `./specs`).
3. **R + packages.** Scoring/consensus/nexus-gen shell out to `Rscript`. The R scripts need `shiny, optparse, dplyr, stringr, ape, testit, phangorn, castor, TreeDist`. Point `R_LIBS` at a library that has them (packages built under R 4.4 load fine under the system R 4.5). Missing packages → `commandLineNex.R` halts on `library(...)`, PAUP gets an empty NEXUS, and **MP4/GA silently produce no tree**.

**Environment variables** (see `CLI.md` § *Environment & tuning* for the full table): `R_LIBS` (R package library), `MB_EXEC` (MrBayes; defaults to `bin/mb`, so unset once `make install-mrbayes` has run), `PCH_SCRATCH` (short temp path), `PCH_ASTRAL_XMX` (ASTRAL heap).

> **`PYTHONPATH` shadow.** A `PYTHONPATH` that contains another project with its own top-level `scripts/` package shadows this repo's `scripts` for the `pch` **console script** (`ModuleNotFoundError: No module named 'scripts.py.cli'`). `python -m scripts.py.cli.main` is immune (cwd wins). Fix: run from a clean `PYTHONPATH`, or invoke via `python -m`.

## Run an experiment end to end

```bash
YAML=experiments/my_run/experiment_specification.yaml
uv run pch simulation "$YAML"              # 1. simulate datasets -> simulation_data/
uv run pch experiment inference "$YAML"    # 2. run inference     -> inference_data/inference_registry.csv
uv run pch experiment score "$YAML"        # 3. FN/FP             -> inference_data/scores.csv
uv run pch experiment status experiments/my_run   # 4. counts by method
```

Step 2 runs every method enabled under the YAML's `methods:` block for every dataset in the sim registry and writes the **generic** registry (one row per dataset×method, keyed by `dataset_id` = the input CSV path). Methods run in dependency order automatically (MP4/GA before ASTRAL3). Inference is source-agnostic — no sim keys, no scoring inline. Step 3 (`pch experiment score`) recovers the model tree via the join and writes FN/FP to `scores.csv`.

### Analyze — join the three tables

The tables are plain CSVs; analysis is a join on `dataset_id`, no bespoke query command.

```python
import polars as pl
sim = pl.read_csv("experiments/my_run/simulation_data/simulated_data_registry.csv")
inf = pl.read_csv("experiments/my_run/inference_data/inference_registry.csv")
scores = pl.read_csv("experiments/my_run/inference_data/scores.csv")
(inf.join(sim, left_on="dataset_id", right_on="path")           # recover sim keys
    .join(scores, on=["dataset_id", "method", "config_hash"]))  # add FN/FP
```

## experiment_folder layout

```
experiments/my_run/
  experiment_specification.yaml       # config — source of truth
  simulation_data/  simulated_data_registry.csv, model trees, configs
  inference_data/
    inference_registry.csv            # THE joinable index (one row per dataset×method)
    scores.csv                        # FN/FP per (dataset_id, method, config_hash) — `pch experiment score`
    shards/{job}.jsonl                # transient per-job staging; removed by compact
    manifest.json                     # created_at, completed_at, methods, tally
```
Everything lives under `experiment_folder/` — self-contained and portable. The point estimate is stored **inline** in the CSV (`point_estimate_newick`), not as a per-run file.

## Reading the registry

One row per **successful** `(dataset, method, config)`, generic and source-agnostic. Columns: `dataset_id` (the input CSV path — the identity), `method, config_hash, method_config_json, runtime_seconds, point_estimate_newick, tree_set_path, consensus_method, status, ran_at, log_path`. No sim keys (join to `simulated_data_registry` on `dataset_id`==`path`) and no FN/FP (see `scores.csv`). Schema: `scripts/py/cli/schemata.py`.

- The registry is the ledger of **successful runs only** — a run is recorded **only if** the command exited 0 **and** produced its point estimate. Failed and dependency-blocked runs are **not** rows; their details are in the per-run `log_path`, and the run prints a tally (`N ok, N skipped, N blocked, N failed`). So `status` is always `ok`, and *absence* of a `(dataset, method)` row means "not successfully done" (failed, blocked, or not yet run).
- `config_hash` is part of the row identity, so the same dataset+method under two configs are distinct rows — they don't overwrite each other.

## Reruns, failures, resuming

Jobs time out and rerun (SLURM 4h cap), often in parallel. The design absorbs this:

- Each job appends to its **own** shard (`shards/{job}.jsonl`) — one writer per shard, no locks.
- `compact` merges shards → `inference_registry.csv`, **last-writer-wins by `ran_at`**, seeds from the existing registry, then deletes shards. `pch experiment inference` compacts at the end; after a bare SLURM batch, run it yourself:

```bash
uv run pch experiment compact experiments/my_run
```

Rerunning is safe and **incremental**: a `(dataset, method, config)` already in the registry is **skipped** (not re-run); a method whose dependency has no successful row yet (this run or a prior one) is **blocked**. The run prints an `ok/skipped/blocked/failed` tally; the registry is the record of what's done (absence = not done).

**Limitation:** resume/gating key on each method's *own* config. Changing an *upstream* method's config does **not** invalidate a downstream method that already succeeded — it keeps its prior row, built from the *old* upstream output. Clear the affected rows (or the registry) when you change an upstream config. (A provenance-aware invalidation is deferred to the SLURM pass.)

## Real (non-simulated) datasets

`pch infer` runs one method on any CSV, simulated or not — the entry is the same generic shape (`dataset_id` = the input path):

```bash
uv run pch infer DATASET.csv OUT_DIR --method mp [--method-config cfg.yaml] [--json]
```
It returns/prints the `InferenceResult`. There is **no registry** for atomic runs — the registry machinery is pipeline-only. Real data has no model tree, so it skips `pch experiment score`; score it with a user-supplied reference (`pch score --estimate … --reference …`).

`--method-config` is a YAML validated against the method's Pydantic model, required for methods with a non-default config (e.g. `pch_astral3` needs `is_exact`). No per-method flags — the same YAML works for atomic and pipeline runs.

## Invariants (agents: respect these)

- **The Python API returns objects; everything renders them.** `api.infer → InferenceResult`, `score → ScoreResult`. The CLI and the registry CSV are renderings. The pipeline calls the API in-process and **never parses CLI stdout**.
- **`api.infer` never raises** — a nonzero exit or missing estimate becomes a `status=failed` `InferenceResult` (never an exception). The pipeline records only successes; failures and dependency-blocks are logged, not written.
- **Order dependency:** heuristic ASTRAL3 needs MP4/GA bipartitions first. Runners declare this via `dependencies()`; the scheduler topo-sorts and gates each run on its dependencies' success in the registry (this run or prior). Don't hand-order methods.
- **Writes are shard-per-job then compact.** Never write `inference_registry.csv` directly from a run; append a shard and let `compact` merge.
- **Config flows through the Pydantic model only** — never redefine a method's params outside its config class.

## Adding a method

See `ARCHITECTURE.md` § *Adding a method* (enum → config → runner → pipeline field → contract/tests).
