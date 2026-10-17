# Migrations

For agents fixing experiment folders made by older code. One entry per breaking change to an on-disk table or `config_hash`; newest first. Table layouts: `SCHEMAS.md`.

## `network_scores` has `bidirectional`

**Affects:** `network_scores.csv`. New column after `guide_tree`: CAMUS's `-B` flag, null for other methods. Uni CAMUS `config_hash` is unchanged. Add it (old CAMUS rows were all unidirectional):

```python
import polars as pl

p = "experiments/my_run/inference_data/network_scores.csv"
df = pl.read_csv(p, infer_schema=False)
bi = pl.when(pl.col("method") == "camus").then(pl.lit("false")).alias("bidirectional")
cols = df.columns
df.with_columns(bi).select(cols[: cols.index("guide_tree") + 1] + ["bidirectional"] + cols[cols.index("guide_tree") + 1 :]).write_csv(p)
```

## TOB-QMC has `alpha` and `three_fix_one_alter`

**Affects:** `tob_qmc` rows, and the BROOQS/NetCS rows built on them. `method_config_json`
`{}` became `{"alpha":1e-07,"three_fix_one_alter":true}`, so `config_hash` changed and
resume reruns `tob_qmc`. Old trees used the bipartition search; the new default uses
`--3f1a`, and every run now passes `-w f`. BROOQS/NetCS hashes did not change, so drop their rows and scores, or they keep
networks built from the old trees:

```python
import polars as pl

for name in ("inference_registry", "scores", "network_scores"):
    p = f"experiments/my_run/inference_data/{name}.csv"
    df = pl.read_csv(p, infer_schema=False)
    df.filter(~pl.col("method").is_in(["tob_qmc", "brooqs", "netcs"])).write_csv(p)
```

## Quartet order is deterministic

**Affects:** rows of quartet-based methods; TREE-QMC (`tob_qmc`) is order-sensitive. Old rows came from an arbitrary per-process quartet order; quartets are now printed sorted, so reruns may not match them. Hashes did not change; drop those rows and rerun to compare.

## TOB-QMC roots on the outgroup

**Affects:** `tob_qmc` rows of experiments with an `outgroup_label`. Old trees are unrooted. `TobQmcConfig` has no fields, so `config_hash` is unchanged and resume skips the old rows. Drop them and their scores, then rerun; the rerun overwrites the trees:

```python
import polars as pl

for name in ("inference_registry", "scores"):
    p = f"experiments/my_run/inference_data/{name}.csv"
    df = pl.read_csv(p, infer_schema=False)
    df.filter(pl.col("method") != "tob_qmc").write_csv(p)
```

## SNaQ start tree is configurable

**Affects:** SNaQ rows. `method_config_json` `{}` became `{"guide_trees":["pch_wastral"]}`, so `config_hash` changed, and output names gain the guide suffix (`N` → `N.pch_wastral`). Old rows no longer match: rerun, or rename the outputs and rewrite the rows (and `network_scores.csv` hashes). From the repo root (registry paths are relative to it):

```python
import sys
from pathlib import Path

import polars as pl

from scripts.lib.experiment import SnaqConfig
from scripts.lib.inference.method_config import hash_config

inf = Path(sys.argv[1])  # experiments/my_run/inference_data
config = SnaqConfig(guide_trees=frozenset({"pch_wastral"}))
new = {"config_hash": hash_config(config), "method_config_json": config.model_dump_json()}
p = inf / "inference_registry.csv"
df = pl.read_csv(p, infer_schema=False)
old = (pl.col("method") == "snaq") & (pl.col("method_config_json") == "{}")
for r in df.filter(old).iter_rows(named=True):
    stem = Path(r["dataset_id"]).stem
    for d in {Path(r["group_estimate_path"]).parent, Path(r["log_path"]).parent}:
        for f in d.glob(f"{stem}[._]*"):
            f.rename(d / f.name.replace(stem, f"{stem}.pch_wastral", 1))
paths = [
    pl.col(c).str.replace(r"/([^/.]+)\.([^/]+)$", "/$1.pch_wastral.$2")
    for c in ["group_estimate_path", "log_path"]
]
df.with_columns(
    pl.when(old).then(e).otherwise(pl.col(e.meta.output_name())) for e in paths
).with_columns(
    pl.when(old).then(pl.lit(v)).otherwise(pl.col(c)).alias(c) for c, v in new.items()
).write_csv(p)
s = inf / "network_scores.csv"  # or delete its snaq rows and rescore
if s.exists():
    sc = pl.read_csv(s, infer_schema=False)
    snaq = (pl.col("method") == "snaq") & (pl.col("guide_tree") == "pch_wastral")
    sc.with_columns(
        config_hash=pl.when(snaq).then(pl.lit(new["config_hash"])).otherwise("config_hash")
    ).write_csv(s)
```

Run as `python <script> experiments/my_run/inference_data`.

## SNaQ point estimate: consistent with the outgroup

**Affects:** SNaQ runs. `N.net` could keep an arbitrary root (outgroup below a hybrid); the family CSV now needs `N.choice`, and a run with no network consistent with the outgroup has no `N.net` and no `is_best` row. Hashes did not change. Per run, then set the registry row's `point_estimate_newick` to the new `N.net` (empty if absent) and rescore:

```bash
JULIA_DEPOT_PATH=bin/julia-depot JULIA_PROJECT=scripts/jl bin/julia scripts/jl/run_snaq.jl --choose N OUT
```

```python
from pathlib import Path
from scripts.lib.inference.runners.snaq import snaq_to_family

snaq_to_family(Path("N.networks"), Path("N.net"), Path("N.choice")).write_csv("N.family.csv")
```

## Network group estimates are family CSVs

**Affects:** every network method's rows in `inference_data/inference_registry.csv` (CAMUS, SNaQ). `group_estimate_path` pointed at the tool's raw output (CAMUS: `<name>.csv`; SNaQ: `<name>.networks`); `network-score` now reads `<name>.family.csv` (`SCHEMAS.md`). Hashes did not change.

Convert each run with its method's converter and repoint its row (or drop the rows and rerun). CAMUS:

```python
from pathlib import Path
from scripts.lib.inference.runners.camus import camus_to_family

camus_to_family(Path("N.csv")).write_csv("N.family.csv")
```

SNaQ: run `run_snaq.jl --choose` for `N.choice`, then `snaq_to_family`, as in "SNaQ point estimate: consistent with the outgroup".

```python
import polars as pl

p = "experiments/my_run/inference_data/inference_registry.csv"
df = pl.read_csv(p, infer_schema=False)
net = pl.col("method").is_in(["camus", "snaq"]) & ~pl.col(  # every network method
    "group_estimate_path"
).str.ends_with(".family.csv")  # rerunnable
df.with_columns(
    group_estimate_path=pl.when(net)
    .then(pl.col("group_estimate_path").str.replace(r"\.(csv|networks)$", ".family.csv"))
    .otherwise(pl.col("group_estimate_path"))
).write_csv(p)
```

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
