# Migrations

For agents fixing experiment folders made by older code. One entry per breaking change to an on-disk table or `config_hash`; newest first. Table layouts: `SCHEMAS.md`.

## `tree_set_path` renamed `group_estimate_path`

**Affects:** `inference_data/inference_registry.csv`. No read-time shim; old files fail the schema.

```python
import polars as pl

p = "experiments/my_run/inference_data/inference_registry.csv"
pl.read_csv(p, infer_schema=False).rename({"tree_set_path": "group_estimate_path"}).write_csv(p)
```

Unmigrated shards (`shards/*.jsonl`) have the old key; run `pch experiment compact` on the old code first, or delete them and rerun.

## CAMUS guide values renamed

**Affects:** CAMUS runs. Guides `astral3` and `wastral` are now `pch_astral3` and `pch_wastral` (YAML `guide_trees:`). The guide is part of the CAMUS config, so every CAMUS `config_hash` changed; old rows never match, so resume would rerun them beside stale ones. `true_tree` is unchanged.

Tree-method hashes did **not** change.

1. Update the YAML: `guide_trees: [pch_astral3, true_tree]`.
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
