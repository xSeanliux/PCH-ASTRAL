# Migrations

For agents fixing experiment folders made by older code. One entry per breaking change to an on-disk table or `config_hash`; newest first. Table layouts: `SCHEMAS.md`.

## `outgroup` renamed `outgroup_label`

**Affects:** YAML `simulation.outgroup:` and `simulation_data/model_graph_registry.csv`. No read-time shim; old files fail the schema.

1. Update the YAML: `outgroup_label: OUT`.
2. Rename the column:

```python
import polars as pl

p = "experiments/my_run/simulation_data/model_graph_registry.csv"
pl.read_csv(p, infer_schema=False).rename({"outgroup": "outgroup_label"}).write_csv(p)
```

## `camus_registry` gains `method`, loses run state

**Affects:** `inference_data/camus_registry.csv`, `inference_data/camus_shards/`. Columns `runtime_seconds`, `status`, `log_path` dropped; `method` added; key now `(dataset_id, method, config_hash, k)`.

Delete both, drop CAMUS rows from `inference_registry.csv` (as in the guide-values entry below; else resume skips the runs and nothing re-ingests), and rerun `pch experiment inference`.

## `tree_set_path` renamed `group_estimate_path`

**Affects:** `inference_data/inference_registry.csv`. No read-time shim; old files fail the schema.

```python
import polars as pl

p = "experiments/my_run/inference_data/inference_registry.csv"
pl.read_csv(p, infer_schema=False).rename({"tree_set_path": "group_estimate_path"}).write_csv(p)
```

Unmigrated shards (`shards/*.jsonl`) have the old key; run `pch experiment compact` on the old code first, or delete them and rerun.

## CAMUS guide values renamed; `outgroup_label` required

**Affects:** CAMUS runs. Guides `astral3` and `wastral` are now `pch_astral3` and `pch_wastral` (YAML `guide_trees:`). The guide is part of the CAMUS config, so every CAMUS `config_hash` changed; old rows never match, so resume would rerun them beside stale ones. `true_tree` is unchanged. The CAMUS block also gains a required `outgroup_label`, equal to `simulation.outgroup_label`; it is hashed too.

Tree-method hashes did **not** change.

1. Update the YAML: `guide_trees: [pch_astral3, true_tree]` and `outgroup_label: OUT`.
2. Drop CAMUS rows:

```python
import polars as pl

p = "experiments/my_run/inference_data/inference_registry.csv"
df = pl.read_csv(p, infer_schema=False)
df.filter(pl.col("method") != "camus").write_csv(p)
```

3. `rm -r experiments/my_run/inference_data/*/CAMUS`
4. Rerun `pch experiment inference`.

Upper layers add their own entries.
