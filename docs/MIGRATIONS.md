# Migrations

For agents fixing experiment folders made by older code. One entry per breaking change to an on-disk table or `config_hash`; newest first. Table layouts: `SCHEMAS.md`.

## `bipartition_strategies: []` means no extra trees

**Affects:** heuristic ASTRAL3 configs with an empty or missing `bipartition_strategies`. It used to mean `mp4_trees` + `ga_trees`; now ASTRAL runs on the quartets alone. The `config_hash` is unchanged, so old rows would wrongly count as done.

To keep the old behaviour, list both strategies in the YAML (this gives a new hash, so the runs rerun). To keep the new behaviour, drop the old ASTRAL3 rows whose `method_config_json` has `"bipartition_strategies":[]` and `"is_exact":false`:

```python
import polars as pl

p = "experiments/my_run/inference_data/inference_registry.csv"
df = pl.read_csv(p, infer_schema=False)
old = (pl.col("method") == "pch_astral3") & pl.col("method_config_json").str.contains(
    '"bipartition_strategies":[],"is_exact":false', literal=True
)
df.filter(~old).write_csv(p)
```

## `outgroup` renamed `outgroup_label`

**Affects:** YAML `simulation.outgroup:` and `simulation_data/model_graph_registry.csv`. No read-time shim; old files fail the schema.

1. Update the YAML: `outgroup_label: OUT`.
2. Rename the column:

```python
import polars as pl

p = "experiments/my_run/simulation_data/model_graph_registry.csv"
pl.read_csv(p, infer_schema=False).rename({"outgroup": "outgroup_label"}).write_csv(p)
```

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
