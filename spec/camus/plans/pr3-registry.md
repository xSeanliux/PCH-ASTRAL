# CAMUS network family registry — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn each CAMUS run's family CSV into rows of one queryable `camus_registry.csv`, keyed by (dataset, guide tree, k).

**Architecture:** CAMUS writes its family as a CSV already, one row per k. A writer reads that CSV right after the run, prepends identity columns, and appends JSON lines to a per-job shard under `inference_data/camus_shards/`. A compaction merges shards into `inference_data/camus_registry.csv`, last writer wins. Same shape as `registry.py`'s shards for tree methods; the merge loop is shared.

**Tech Stack:** Python 3.12, polars, pytest. Type checker `ty`, linter `ruff`.

**Spec:** `spec/camus/PLAN.md` (section "PR 3") and `spec/camus/registry.md`. Terms in `CONTEXT.md`.

## Global Constraints

- Run tests with `uv run python -m pytest tests/ -q`; type-check with `uv run ty check scripts/lib scripts/py`; lint with `uv run ruff check` and `uv run ruff format`. All three clean before commit.
- No `Any`, no `object` as a type, no `# type: ignore` on lines that can be typed (user rule).
- Keep prose brief: comments and docstrings say why, not what.
- CAMUS CSV header, exactly: `Number of Branches,Quartet Satisfied Percent,Extended Newick`. Row k = 0 is the guide tree. A family may be one row.
- Registry column names: `dataset_id, guide_tree, config_hash, runtime_seconds, status, ran_at, log_path, k, qsat_percent, network_newick`.
- Registry dedup key: `dataset_id | config_hash | k`; last writer wins by `ran_at`.
- Store only rows CAMUS wrote; pad nothing.
- `runtime_seconds` is the whole family's time, repeated on every row.
- Ingest first, then `registry.write_result`. If ingestion fails: warn, count `failed`, write no inference row, so the next run retries.
- Compact CAMUS shards only when `inference_data/camus_shards/` or `camus_registry.csv` exists, so tree-only experiments never get an empty file.
- Commit messages: Conventional Commits, end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

1. A family CSV whose header differs from the three expected names (a future CAMUS changes it): must raise, never ingest garbage. Pinned by Task 1's `test_write_family_rejects_unexpected_header`.
2. A newick containing commas and `#H1` labels survives CSV → JSON line → CSV unchanged. Pinned by Task 1's round-trip assertion on `network_newick`.
3. A requeued job ingests the same family twice: compact keeps one row per k, not two. Pinned by Task 1's dedup test.
4. Ingestion fails after CAMUS exited 0: no `inference_registry` row, `failed` tally, next run retries. Pinned by Task 2's `test_handle_inference_skips_inference_row_when_ingest_fails`.
5. A tree-only experiment compacts without creating `camus_registry.csv`. Pinned by Task 2's `test_compact_without_camus_writes_no_camus_registry`.

---

### Task 1: `camus_registry.py` — write a family, compact the shards

**Files:**
- Modify: `scripts/py/cli/schemata.py` (add `CAMUS_REGISTRY_SCHEMA` after `INFERENCE_REGISTRY_SCHEMA`)
- Modify: `scripts/lib/inference/registry.py` (share the merge loop)
- Create: `scripts/lib/inference/camus_registry.py`
- Test: `tests/scripts/lib/inference/test_camus_registry.py`

**Interfaces:**
- Consumes: `InferenceResult` (`scripts/lib/inference/inference.py`): `dataset_id`, `config_hash`, `runtime_seconds`, `status` (a `RunStatus`), `ran_at`, `log_path`, `tree_set_path` (the family CSV path for a CAMUS run). `registry.current_shard_id()`, `registry._ran_at`, `registry._iter_shard_rows`.
- Produces: `camus_registry.write_family(result: InferenceResult, guide_tree: str, experiment_folder: Path) -> Path` and `camus_registry.compact(experiment_folder: Path, *, cleanup: bool = True) -> Path`. `camus_registry.CAMUS_COLUMNS = ["Number of Branches", "Quartet Satisfied Percent", "Extended Newick"]`. `camus_registry.registry_path(experiment_folder) -> Path` and `camus_registry.shards_dir(experiment_folder) -> Path`.

- [ ] **Step 1: Add the schema**

In `scripts/py/cli/schemata.py`, after `INFERENCE_REGISTRY_SCHEMA`:

```python
# One row per (dataset, guide tree, k) from a CAMUS run: its network family.
CAMUS_REGISTRY_SCHEMA = pl.Schema(
    {
        "dataset_id": String,
        "guide_tree": String,
        "config_hash": String,
        "runtime_seconds": Float64,  # the whole family's; repeated per row
        "status": String,
        "ran_at": String,
        "log_path": String,
        "k": Int64,
        "qsat_percent": Float64,
        "network_newick": String,
    }
)
```

- [ ] **Step 2: Share the merge loop in `registry.py`**

`registry.compact` seeds from the existing CSV, folds shard rows last-writer-wins by `ran_at`, writes, and cleans up. Pull that into a helper both registries call. Replace the body of `compact` so it reads:

```python
def compact(experiment_folder: Path, *, cleanup: bool = True) -> Path:
    """Merge shards/*.jsonl -> inference_registry.csv (last-writer-wins by ran_at).

    Idempotent. With cleanup=True (default) the shard files are removed after a
    successful merge so no staging junk remains.
    """
    return merge_shards(
        _shards_dir(experiment_folder),
        registry_path(experiment_folder),
        INFERENCE_REGISTRY_SCHEMA,
        run_key,
        cleanup=cleanup,
    )


def merge_shards(
    shards: Path,
    out: Path,
    schema: pl.Schema,
    key: Callable[[Mapping[str, object]], str],
    *,
    cleanup: bool = True,
) -> Path:
    """Fold shards/*.jsonl into `out` under `schema`, one row per `key`, the
    newest `ran_at` winning. Seeds from an existing `out` so incremental
    compaction accumulates. Removes the shards afterwards when `cleanup`."""
    by_key: dict[str, dict[str, Cell]] = {}
    if out.exists():
        for prev_row in pl.read_csv(out, schema=schema).iter_rows(named=True):
            by_key[key(prev_row)] = prev_row

    shard_files = sorted(shards.glob("*.jsonl")) if shards.exists() else []
    for row in _iter_shard_rows(shards):
        k = key(row)
        prev = by_key.get(k)
        if prev is None or _ran_at(row) >= _ran_at(prev):
            by_key[k] = row

    out.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(list(by_key.values()), schema=schema).write_csv(out)

    if cleanup:
        for sf in shard_files:
            sf.unlink()
        if shards.exists() and not any(shards.iterdir()):
            shards.rmdir()
    return out
```

Change `_iter_shard_rows` to take the shard directory (`def _iter_shard_rows(shards: Path)`) instead of the experiment folder; its body already computes `shards` on its first line, so drop that line. Import `Callable` from `collections.abc`. Existing `test_registry.py` tests must still pass unchanged.

- [ ] **Step 3: Write the failing tests**

`tests/scripts/lib/inference/test_camus_registry.py`:

```python
from datetime import datetime, timezone
from pathlib import Path

import polars as pl
import pytest

from scripts.lib.inference import camus_registry
from scripts.lib.inference.inference import (
    InferenceResult,
    NetworkInferenceMethod,
    RunStatus,
)
from scripts.py.cli.schemata import CAMUS_REGISTRY_SCHEMA

NEWICKS = [
    "(((A,B),(C,D)),OUT);",
    "(((A,(B)#H1),((#H1,C),D)),OUT);",
]
FAMILY = (
    "Number of Branches,Quartet Satisfied Percent,Extended Newick\n"
    f'0,0,"{NEWICKS[0]}"\n'
    f'1,36.86453576864536,"{NEWICKS[1]}"\n'
)


def _result(tmp_path: Path, family: str = FAMILY, ran_at: str | None = None) -> InferenceResult:
    csv = tmp_path / "out" / "CAMUS" / "networks" / "sim_1_1_1.true_tree.csv"
    csv.parent.mkdir(parents=True, exist_ok=True)
    csv.write_text(family)
    return InferenceResult(
        dataset_id="sim/sim_1_1_1.csv",
        tree_inference_method=NetworkInferenceMethod.CAMUS,
        config_hash="abc",
        method_config_json="{}",
        point_estimate_newick="",
        runtime_seconds=3.5,
        status=RunStatus.OK,
        ran_at=ran_at or datetime.now(timezone.utc).isoformat(),
        tree_set_path=str(csv),
        log_path=str(tmp_path / "out" / "CAMUS" / "logs" / "sim_1_1_1.true_tree.log"),
    )


def test_write_family_appends_one_row_per_k(tmp_path: Path):
    shard = camus_registry.write_family(_result(tmp_path), "true_tree", tmp_path)
    assert shard.parent == camus_registry.shards_dir(tmp_path)
    assert len(shard.read_text().splitlines()) == 2


def test_compact_renames_columns_and_keeps_newicks_intact(tmp_path: Path):
    camus_registry.write_family(_result(tmp_path), "true_tree", tmp_path)
    out = camus_registry.compact(tmp_path)

    assert out == camus_registry.registry_path(tmp_path)
    df = pl.read_csv(out, schema=CAMUS_REGISTRY_SCHEMA).sort("k")
    assert df.columns == list(CAMUS_REGISTRY_SCHEMA.keys())
    assert df["k"].to_list() == [0, 1]
    assert df["qsat_percent"].to_list() == pytest.approx([0.0, 36.86453576864536])
    assert df["network_newick"].to_list() == NEWICKS
    assert df["guide_tree"].to_list() == ["true_tree"] * 2
    assert df["runtime_seconds"].to_list() == [3.5, 3.5]
    assert df["status"].to_list() == ["ok", "ok"]


def test_a_family_of_one_row_is_fine(tmp_path: Path):
    one = FAMILY.splitlines()[0] + "\n" + FAMILY.splitlines()[1] + "\n"
    camus_registry.write_family(_result(tmp_path, family=one), "true_tree", tmp_path)
    df = pl.read_csv(camus_registry.compact(tmp_path), schema=CAMUS_REGISTRY_SCHEMA)
    assert df["k"].to_list() == [0]


def test_write_family_rejects_unexpected_header(tmp_path: Path):
    bad = FAMILY.replace("Extended Newick", "Newick")
    with pytest.raises(ValueError, match="header"):
        camus_registry.write_family(_result(tmp_path, family=bad), "true_tree", tmp_path)
    assert not camus_registry.shards_dir(tmp_path).exists()


def test_write_family_rejects_a_missing_family(tmp_path: Path):
    result = _result(tmp_path)
    Path(str(result.tree_set_path)).unlink()
    with pytest.raises(ValueError):
        camus_registry.write_family(result, "true_tree", tmp_path)


def test_compact_dedups_a_requeued_family_keeping_the_newest(tmp_path: Path):
    camus_registry.write_family(
        _result(tmp_path, ran_at="2026-09-29T00:00:00+00:00"), "true_tree", tmp_path
    )
    camus_registry.compact(tmp_path)
    newer = FAMILY.replace("36.86453576864536", "40.0")
    camus_registry.write_family(
        _result(tmp_path, family=newer, ran_at="2026-09-29T01:00:00+00:00"),
        "true_tree",
        tmp_path,
    )
    df = pl.read_csv(camus_registry.compact(tmp_path), schema=CAMUS_REGISTRY_SCHEMA)
    assert df.height == 2
    assert df.filter(pl.col("k") == 1)["qsat_percent"][0] == pytest.approx(40.0)


def test_compact_removes_shards(tmp_path: Path):
    camus_registry.write_family(_result(tmp_path), "true_tree", tmp_path)
    camus_registry.compact(tmp_path)
    assert not camus_registry.shards_dir(tmp_path).exists()
```

- [ ] **Step 4: Run the tests to see them fail**

Run: `uv run python -m pytest tests/scripts/lib/inference/test_camus_registry.py -q`
Expected: FAIL with `ImportError` (no module `camus_registry`).

- [ ] **Step 5: Implement `camus_registry.py`**

```python
"""The network family registry: one row per (dataset, guide tree, k).

CAMUS writes each run's family as a CSV. `write_family` reads it, prepends the
run's identity, and appends JSON lines to this job's shard; `compact` merges
the shards into camus_registry.csv. Same shard/compact shape as `registry`.
"""

import json
from pathlib import Path

import polars as pl

from scripts.lib.inference import registry
from scripts.lib.inference.inference import InferenceResult
from scripts.py.cli.schemata import CAMUS_REGISTRY_SCHEMA

# CAMUS's own header, in order. Anything else is a CAMUS we do not know.
CAMUS_COLUMNS = ["Number of Branches", "Quartet Satisfied Percent", "Extended Newick"]
_RENAME = dict(zip(CAMUS_COLUMNS, ["k", "qsat_percent", "network_newick"]))
_KEY_COLUMNS = ["dataset_id", "config_hash", "k"]


def shards_dir(experiment_folder: Path) -> Path:
    return experiment_folder / "inference_data" / "camus_shards"


def registry_path(experiment_folder: Path) -> Path:
    return experiment_folder / "inference_data" / "camus_registry.csv"


def _family_key(row: Mapping[str, object]) -> str:
    return "|".join(str(row.get(c)) for c in _KEY_COLUMNS)


def write_family(result: InferenceResult, guide_tree: str, experiment_folder: Path) -> Path:
    """Append the run's family, one JSON line per k, to this job's shard.

    Raises ValueError when the family is missing or its header is not CAMUS's,
    so the caller can count the run as failed and let the next run retry."""
    if result.tree_set_path is None or not Path(result.tree_set_path).is_file():
        raise ValueError(f"no network family at {result.tree_set_path}")
    family = pl.read_csv(result.tree_set_path)
    if family.columns != CAMUS_COLUMNS:
        raise ValueError(f"unexpected family header {family.columns}; want {CAMUS_COLUMNS}")
    identity = {
        "dataset_id": result.dataset_id,
        "guide_tree": guide_tree,
        "config_hash": result.config_hash,
        "runtime_seconds": result.runtime_seconds,
        "status": result.status.value,
        "ran_at": result.ran_at,
        "log_path": result.log_path,
    }
    shards = shards_dir(experiment_folder)
    shards.mkdir(parents=True, exist_ok=True)
    shard = shards / f"{registry.current_shard_id()}.jsonl"
    with shard.open("a") as f:
        for row in family.rename(_RENAME).iter_rows(named=True):
            f.write(json.dumps({**identity, **row}) + "\n")
    return shard


def compact(experiment_folder: Path, *, cleanup: bool = True) -> Path:
    """Merge camus_shards/*.jsonl -> camus_registry.csv, one row per
    (dataset, config, k), the newest ran_at winning."""
    return registry.merge_shards(
        shards_dir(experiment_folder),
        registry_path(experiment_folder),
        CAMUS_REGISTRY_SCHEMA,
        _family_key,
        cleanup=cleanup,
    )
```

Add `from collections.abc import Mapping` to the imports.

- [ ] **Step 6: Run the tests to see them pass**

Run: `uv run python -m pytest tests/scripts/lib/inference/test_camus_registry.py tests/scripts/lib/inference/test_registry.py -q`
Expected: all PASS.

- [ ] **Step 7: Lint, type-check, commit**

```bash
uv run ruff format scripts/lib scripts/py tests/scripts/lib/inference/test_camus_registry.py
uv run ruff check scripts/lib scripts/py tests/scripts/lib/inference/test_camus_registry.py
uv run ty check scripts/lib scripts/py
git add scripts/py/cli/schemata.py scripts/lib/inference/registry.py scripts/lib/inference/camus_registry.py tests/scripts/lib/inference/test_camus_registry.py
git commit -m "feat(camus): network family registry: write a family, compact the shards"
```

---

### Task 2: Wire ingestion and compaction into the pipeline

**Files:**
- Modify: `scripts/py/cli/handle_inference.py` (the run loop, lines ~118–136, and the compact branch at the end)
- Modify: `scripts/lib/inference/executor.py` (`run_compact`, lines ~100–117)
- Test: `tests/scripts/py/cli/test_handle_inference.py`, `tests/scripts/lib/inference/test_executor.py`

**Interfaces:**
- Consumes: `camus_registry.write_family(result, guide_tree, experiment_folder)` (raises `ValueError` on a bad family), `camus_registry.compact(experiment_folder)`, `camus_registry.shards_dir`, `camus_registry.registry_path` from Task 1. `variants(cfg)` in `handle_inference.py` yields `(cfg, suffix)`; for CAMUS the suffix is the guide tree's value. `NetworkInferenceMethod` from `scripts/lib/inference/inference.py`.
- Produces: nothing new; behaviour only.

- [ ] **Step 1: Write the failing tests**

Append to `tests/scripts/py/cli/test_handle_inference.py` (it already has `_config`, `InferenceResult`, `RunStatus`, `registry`, `config_hash`, `api`, `pl`, `datetime`, `timezone` imported; add `from scripts.lib.inference import camus_registry` and `from scripts.py.cli.schemata import CAMUS_REGISTRY_SCHEMA`):

```python
FAMILY = (
    "Number of Branches,Quartet Satisfied Percent,Extended Newick\n"
    '0,0,"((A,B),OUT);"\n'
    '1,50.0,"((A,(B)#H1),(#H1,OUT));"\n'
)


def _camus_experiment(tmp_path: Path) -> Path:
    cond_dir = tmp_path / "simulation_data" / "simulated_data" / "high_0.1_4_320"
    cond_dir.mkdir(parents=True)
    dataset = cond_dir / "sim_1_1_1.csv"
    dataset.write_text("id,feature,weight,A,B,OUT\n")
    pl.DataFrame(
        {
            "poly_level": ["high"],
            "character_count": [320],
            "min_tree_height": [4],
            "homoplasy_factor": [0.1],
            "horizontal_edges": [1],
            "model_tree": [1],
            "replica": [1],
            "path": [str(dataset)],
        }
    ).write_csv(tmp_path / "simulation_data" / "simulated_data_registry.csv")
    return dataset


def _fake_camus(family: str):
    def fake(input_csv, output_dir, method, config, *, name=None):
        csv = output_dir / "CAMUS" / "networks" / f"{name}.csv"
        csv.parent.mkdir(parents=True, exist_ok=True)
        csv.write_text(family)
        return InferenceResult(
            dataset_id=registry.canonical_path(input_csv),
            tree_inference_method=method,
            config_hash=config_hash(config),
            method_config_json=config.model_dump_json(),
            point_estimate_newick="",
            runtime_seconds=1.0,
            status=RunStatus.OK,
            ran_at=datetime.now(timezone.utc).isoformat(),
            tree_set_path=str(csv),
        )

    return fake


def test_handle_inference_ingests_each_camus_family(tmp_path: Path, monkeypatch):
    dataset = _camus_experiment(tmp_path)
    monkeypatch.setattr(api, "infer", _fake_camus(FAMILY))
    methods = {"camus": {"guide_trees": ["true_tree"]}}
    cfg = ExperimentConfig.model_validate(_config(tmp_path, methods=methods))
    out = handle_inference(cfg)

    assert pl.read_csv(out).height == 1  # the inference row
    df = pl.read_csv(camus_registry.registry_path(tmp_path), schema=CAMUS_REGISTRY_SCHEMA)
    assert df.height == 2
    assert df["guide_tree"].to_list() == ["true_tree", "true_tree"]
    assert sorted(df["k"].to_list()) == [0, 1]
    assert df["dataset_id"][0] == registry.canonical_path(dataset)
    assert not camus_registry.shards_dir(tmp_path).exists()  # compacted


def test_handle_inference_skips_inference_row_when_ingest_fails(tmp_path: Path, monkeypatch, capsys):
    _camus_experiment(tmp_path)
    monkeypatch.setattr(api, "infer", _fake_camus(FAMILY.replace("Extended Newick", "Newick")))
    methods = {"camus": {"guide_trees": ["true_tree"]}}
    cfg = ExperimentConfig.model_validate(_config(tmp_path, methods=methods))
    out = handle_inference(cfg)

    assert pl.read_csv(out).height == 0  # no inference row: the next run retries
    assert not camus_registry.registry_path(tmp_path).exists()
    assert "failed" in capsys.readouterr().out


def test_compact_without_camus_writes_no_camus_registry(tmp_path: Path, monkeypatch):
    # An mp-only experiment; reuse the fixture the other tests use.
    sim_dir = tmp_path / "simulation_data" / "simulated_data" / "high_0.1_4_320"
    sim_dir.mkdir(parents=True)
    dataset = sim_dir / "sim_0_1_1.csv"
    dataset.write_text("id,feature,weight,A,B\n")
    pl.DataFrame(
        {
            "poly_level": ["high"],
            "character_count": [320],
            "min_tree_height": [4],
            "homoplasy_factor": [0.1],
            "horizontal_edges": [0],
            "model_tree": [1],
            "replica": [1],
            "path": [str(dataset)],
        }
    ).write_csv(tmp_path / "simulation_data" / "simulated_data_registry.csv")

    def fake(input_csv, output_dir, method, config, *, name=None):
        return InferenceResult(
            dataset_id=registry.canonical_path(input_csv),
            tree_inference_method=method,
            config_hash="h",
            method_config_json="{}",
            point_estimate_newick="(A,B);",
            runtime_seconds=1.0,
            status=RunStatus.OK,
            ran_at=datetime.now(timezone.utc).isoformat(),
        )

    monkeypatch.setattr(api, "infer", fake)
    handle_inference(ExperimentConfig.model_validate(_config(tmp_path)))
    assert not camus_registry.registry_path(tmp_path).exists()
```

In `tests/scripts/lib/inference/test_executor.py`, find the existing test of `run_compact` (search `run_compact`). Add beside it one test that writes a CAMUS shard by hand and asserts `run_compact` produces `camus_registry.csv`:

```python
def test_run_compact_also_compacts_camus_shards(tmp_path: Path, monkeypatch):
    # Mirror the setup of the neighbouring run_compact test for the spec file and
    # experiment folder, then:
    shards = camus_registry.shards_dir(folder)
    shards.mkdir(parents=True)
    row = {
        "dataset_id": "d.csv", "guide_tree": "true_tree", "config_hash": "h",
        "runtime_seconds": 1.0, "status": "ok", "ran_at": "2026-09-29T00:00:00+00:00",
        "log_path": None, "k": 0, "qsat_percent": 0.0, "network_newick": "((A,B),OUT);",
    }
    (shards / "job.jsonl").write_text(json.dumps(row) + "\n")
    run_compact(str(spec_path))
    assert pl.read_csv(camus_registry.registry_path(folder), schema=CAMUS_REGISTRY_SCHEMA).height == 1
    assert not shards.exists()
```

(`folder` and `spec_path` come from the neighbouring test's setup; copy that setup rather than referencing its locals.)

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run python -m pytest tests/scripts/py/cli/test_handle_inference.py tests/scripts/lib/inference/test_executor.py -q`
Expected: the three new `handle_inference` tests and the executor test FAIL (no `camus_registry.csv`; the ingest-failure test finds an inference row).

- [ ] **Step 3: Wire `handle_inference`**

In the run loop, after `result = api.infer(...)` and the `status is not RunStatus.OK` branch, before `registry.write_result`:

```python
                if isinstance(m, NetworkInferenceMethod):
                    # Ingest first: an inference row with no family would make
                    # resume skip this unit forever.
                    try:
                        camus_registry.write_family(result, str(suffix), experiment_folder)
                    except ValueError as e:
                        print(f"[yellow]{m.value} failed on {input_path.name}: {e}[/yellow]")
                        tally["failed"] += 1
                        continue
```

At the end, in the `else` branch that compacts:

```python
        out = registry.compact(experiment_folder)
        if camus_registry.shards_dir(experiment_folder).exists() or camus_registry.registry_path(experiment_folder).exists():
            camus_registry.compact(experiment_folder)
```

Put that guard in one place both callers use: add to `camus_registry.py`

```python
def compact_if_any(experiment_folder: Path) -> Path | None:
    """Compact when this experiment has ever run CAMUS; else leave no file behind."""
    if shards_dir(experiment_folder).exists() or registry_path(experiment_folder).exists():
        return compact(experiment_folder)
    return None
```

and call `camus_registry.compact_if_any(experiment_folder)` from both `handle_inference` and `executor.run_compact` (after `registry.compact(folder)`).

Imports: `from scripts.lib.inference import camus_registry` and `NetworkInferenceMethod` in `handle_inference.py`; `camus_registry` in `executor.py`.

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run python -m pytest tests/ -q`
Expected: all PASS.

- [ ] **Step 5: Lint, type-check, commit**

```bash
uv run ruff format scripts/lib scripts/py tests/scripts/py/cli/test_handle_inference.py tests/scripts/lib/inference/test_executor.py
uv run ruff check scripts/lib scripts/py tests/scripts/py/cli/test_handle_inference.py tests/scripts/lib/inference/test_executor.py
uv run ty check scripts/lib scripts/py
git add scripts/lib/inference/camus_registry.py scripts/py/cli/handle_inference.py scripts/lib/inference/executor.py tests/scripts/py/cli/test_handle_inference.py tests/scripts/lib/inference/test_executor.py
git commit -m "feat(camus): ingest each network family and compact camus_registry.csv"
```
