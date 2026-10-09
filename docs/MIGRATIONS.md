# Migrations

For agents fixing experiment folders made by older code. One entry per breaking change to an on-disk table or `config_hash`; newest first. Table layouts: `SCHEMAS.md`.

## Network group estimates are family CSVs

**Affects:** CAMUS and SNaQ rows in `inference_data/inference_registry.csv`. `group_estimate_path` pointed at CAMUS's raw `<name>.csv` or SNaQ's `<name>.networks`; `network-score` now reads `<name>.family.csv` (`SCHEMAS.md`). Hashes did not change.

Convert each run and repoint its row (or drop the rows and rerun):

```bash
python -m scripts.py.camus_family --input N.csv --output N.family.csv
python -m scripts.py.snaq_family --networks N.networks --best N.net --output N.family.csv
```

```python
import polars as pl

p = "experiments/my_run/inference_data/inference_registry.csv"
df = pl.read_csv(p, infer_schema=False)
net = pl.col("method").is_in(["camus", "snaq"]) & ~pl.col(
    "group_estimate_path"
).str.ends_with(".family.csv")  # rerunnable
df.with_columns(
    group_estimate_path=pl.when(net)
    .then(pl.col("group_estimate_path").str.replace(r"\.(csv|networks)$", ".family.csv"))
    .otherwise(pl.col("group_estimate_path"))
).write_csv(p)
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
