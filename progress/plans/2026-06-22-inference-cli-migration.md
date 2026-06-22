# Inference CLI/YAML Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the ad-hoc bash inference pipeline with a config-driven `inference` CLI command that reads an experiment YAML, runs the requested inference methods over the simulation registry, and writes a joinable results registry — starting with a fully working MP4 slice.

**Architecture:** Mirror the existing `simulation` command exactly (`scripts/py/cli/main.py` → `handle_simulation`). A new `handle_inference(config)` reads `{experiment_folder}/simulation_data/simulated_data_registry.csv`, selects enabled methods from `config.methods`, and for each `(dataset, method)` pair shells out to a per-method runner (reusing the validated `scripts/sh/run*.sh` scripts), times it, and assembles an `InferenceResult`. Results are written to `{experiment_folder}/inference_data/inference_registry.csv` whose join keys match the simulation registry, so the two can be joined for analysis. Method-specific command construction lives in a pure `runners.py` module so it is unit-testable without external binaries.

**Tech Stack:** Python 3.12 (uv), Typer (CLI), Pydantic v2 (`ExperimentConfig`), Polars (registry I/O), `rich` (progress/printing), `shortuuid` (run IDs), `subprocess` (shelling to bash runners), pytest.

**Source spec:** `specs/cli_specs/human_specs.md`. Method descriptions: `docs/KEYS.md`. Legacy script catalogue (what inference must reproduce): `docs/HOW_TO_RUN.md`.

## Global Constraints

- **Python 3.12, managed with uv.** Run tests with `uv run python -m pytest`, type-check with `make py-static` (ty), format with `make py-fmt` (ruff), lint with `make py-lint`.
- **Tests mirror `scripts/` under `tests/`** (e.g. `scripts/lib/inference/inference.py` → `tests/scripts/lib/inference/test_inference.py`). No `__init__.py` needed — the project uses implicit namespace packages (confirmed: `scripts/py/cli/` and `scripts/lib/inference/` have none).
- **Registry join keys must match the simulation registry verbatim** (`scripts/py/cli/schemata.py`): `poly_level, character_count, min_tree_height, homoplasy_factor, horizontal_edges, model_tree, replica`. This is the whole point of the registry per `docs/KEYS.md` — inference rows must join to simulation rows on these columns.
- **Brevity (repo CLAUDE.md):** keep code, comments, and docs tight — if removing a word loses nothing, remove it.
- **Reuse the bash runners, do not reimplement** PAUP/MrBayes/ASTRAL orchestration in Python for this milestone. `handle_simulation` shells out to `java -jar ...`; inference shells out to `bash scripts/sh/run*.sh` the same way.
- **`ruff` ignores `E741`** (see `pyproject.toml`); otherwise default rules.

---

## Migration Roadmap (what needs doing, end to end)

The full migration is too large for one placeholder-free plan, so it is split into milestones. **Each milestone produces working, testable software on its own.** This document fully specifies **Milestone 1**; Milestones 2–5 are scoped here and should each be expanded into their own plan (via this same skill) when reached.

| Milestone | Deliverable | Status |
|-----------|-------------|--------|
| **M1 — MP4 slice + scaffolding** | `inference` CLI runs MP4 across the sim registry and writes `inference_registry.csv`. Establishes the runner abstraction, result dataclass, and registry schema. | **Detailed below** |
| **M2 — GA + ASTRAL3 runners** | Add Gray-Atkinson and ASTRAL III (heuristic + exact). ASTRAL3 is order-dependent — its bipartition strategies (`mp4_trees`, `ga_trees`) require MP4/GA to have run first (see `docs/HOW_TO_RUN.md`); the orchestrator must sequence methods accordingly. Reconcile the stale `printQuartets.py -q` interface (`runASTRAL.sh` calls `-q`; current script takes `-i`/`-w`). | Scoped below |
| **M3 — Scoring & metrics** | Populate `fn_rate`/`fp_rate` in the registry by scoring each point estimate against its true tree via `scripts/R/RFScorer.R` (the model tree is resolvable from `model_graph_registry.csv` by `(horizontal_edges, model_tree)`). Add per-run runtime breakdown. | Scoped below |
| **M4 — wASTRAL + TREE-QMC** | Add the two methods with no existing bash runner. Requires discovering the binary interfaces installed by `scripts/sh/installs/install_aster.sh` and `install_w_tree_qmc.sh`, and wiring `WeightedASTRALConfig` / `WeightedTreeQMCConfig`. PCH-W quartets already exist (`printQuartets.py -w`). | Scoped below |
| **M5 — SLURM orchestration** | Submit `(dataset, method)` jobs to SLURM instead of running them inline, replacing `run_parallel_sim.sh`. Job dependencies for order-dependent methods (M2). | Scoped below |

---

## File Structure (Milestone 1)

- **Modify** `scripts/lib/inference/inference.py` — fix the `metadata` mutable-default crash; add optional breadcrumb fields and `to_registry_row()`.
- **Modify** `scripts/py/cli/schemata.py` — add `INFERENCE_REGISTRY_SCHEMA`.
- **Create** `scripts/lib/inference/runners.py` — pure per-method command + artifact-path construction (MP4 only in M1).
- **Create** `scripts/py/cli/handle_inference.py` — orchestration, mirroring `handle_simulation.py`.
- **Modify** `scripts/py/cli/main.py` — wire the `inference` command to `handle_inference`.
- **Modify** `experiments/README.md` and `docs/CLI.md` — document the now-working `inference` command.
- **Create** tests: `tests/scripts/lib/inference/test_inference.py`, `tests/scripts/lib/inference/test_runners.py`, `tests/scripts/py/cli/test_handle_inference.py`.

---

### Task 1: Fix `InferenceResult` and add registry serialization

The dataclass currently crashes on import: `metadata: dict[str, str] = {}` raises `ValueError: mutable default <class 'dict'> for field metadata is not allowed`. Fix it, add the breadcrumb fields the spec asks for (log path, FN/FP metrics — nullable, populated in M3), and a method that converts a result into a registry row keyed to match the simulation registry.

**Files:**
- Modify: `scripts/lib/inference/inference.py`
- Test: `tests/scripts/lib/inference/test_inference.py`

**Interfaces:**
- Consumes: `Polymorphism` from `scripts.lib.types`.
- Produces:
  - `TreeInferenceMethod(StrEnum)` with members `PCH_ASTRAL3="pch_astral3"`, `PCH_WASTRAL="pch_wastral"`, `PCH_W_TREE_QMC="pch_w_tree_qmc"`, `MP="mp"`, `GA="ga"`.
  - `InferenceResult` dataclass (fields below) with `to_registry_row(self) -> dict[str, object]`.

- [ ] **Step 1: Write the failing test**

Create `tests/scripts/lib/inference/test_inference.py`:

```python
from datetime import timedelta
from pathlib import Path

from scripts.lib.inference.inference import InferenceResult, TreeInferenceMethod
from scripts.lib.types import Polymorphism


def _make_result() -> InferenceResult:
    return InferenceResult(
        target_tree=1,
        ret_edges=0,
        replica=2,
        poly=Polymorphism.HIGH,
        tree_height=4,
        homoplasy_factor=0.1,
        n_chars=320,
        tree_inference_method=TreeInferenceMethod.MP,
        runtime=timedelta(seconds=12.5),
        point_estimate_path=Path("out/MP4/trees/sim_0_1_2-maj.tree"),
        group_estimate_path=Path("out/MP4/trees/sim_0_1_2.trees"),
        consensus_method="majority",
    )


def test_inference_result_constructs_with_default_metadata():
    # Regression: a mutable default `{}` on the dataclass field crashes at import.
    result = _make_result()
    assert result.metadata == {}
    assert result.fn_rate is None and result.fp_rate is None


def test_to_registry_row_uses_simulation_join_keys():
    row = _make_result().to_registry_row()
    assert row["poly_level"] == "high"
    assert row["character_count"] == 320
    assert row["min_tree_height"] == 4
    assert row["homoplasy_factor"] == 0.1
    assert row["horizontal_edges"] == 0
    assert row["model_tree"] == 1
    assert row["replica"] == 2
    assert row["method"] == "mp"
    assert row["runtime_seconds"] == 12.5
    assert row["point_estimate_path"] == "out/MP4/trees/sim_0_1_2-maj.tree"
    assert row["group_estimate_path"] == "out/MP4/trees/sim_0_1_2.trees"
    assert row["consensus_method"] == "majority"
    assert row["fn_rate"] is None and row["fp_rate"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/scripts/lib/inference/test_inference.py -v`
Expected: collection/import error — `ValueError: mutable default <class 'dict'> for field metadata is not allowed`.

- [ ] **Step 3: Rewrite the module**

Replace the entire contents of `scripts/lib/inference/inference.py`:

```python
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum
from pathlib import Path
from typing import Optional

from scripts.lib.types import Polymorphism


class TreeInferenceMethod(StrEnum):
    PCH_ASTRAL3 = "pch_astral3"
    PCH_WASTRAL = "pch_wastral"
    PCH_W_TREE_QMC = "pch_w_tree_qmc"
    MP = "mp"
    GA = "ga"


@dataclass
class InferenceResult:
    """One inference run: its dataset/config join keys, the method, and its artifacts."""

    # join keys (match scripts/py/cli/schemata.py CONFIG_KEY + MODEL_NETWORK_KEY)
    target_tree: int
    ret_edges: int
    replica: int
    poly: Polymorphism
    tree_height: int
    homoplasy_factor: float
    n_chars: int

    tree_inference_method: TreeInferenceMethod
    runtime: timedelta
    point_estimate_path: Path

    group_estimate_path: Optional[Path] = None  # methods that return multiple trees
    consensus_method: Optional[str] = None  # how the group was reduced to a point
    log_path: Optional[Path] = None

    # metrics, populated by the scoring milestone (M3)
    fn_rate: Optional[float] = None
    fp_rate: Optional[float] = None

    metadata: dict[str, str] = field(default_factory=dict)

    def to_registry_row(self) -> dict[str, object]:
        return {
            "poly_level": self.poly.value,
            "character_count": self.n_chars,
            "min_tree_height": self.tree_height,
            "homoplasy_factor": self.homoplasy_factor,
            "horizontal_edges": self.ret_edges,
            "model_tree": self.target_tree,
            "replica": self.replica,
            "method": self.tree_inference_method.value,
            "runtime_seconds": self.runtime.total_seconds(),
            "point_estimate_path": str(self.point_estimate_path),
            "group_estimate_path": (
                str(self.group_estimate_path) if self.group_estimate_path else None
            ),
            "consensus_method": self.consensus_method,
            "log_path": str(self.log_path) if self.log_path else None,
            "fn_rate": self.fn_rate,
            "fp_rate": self.fp_rate,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/scripts/lib/inference/test_inference.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/inference/inference.py tests/scripts/lib/inference/test_inference.py
git commit -m "fix: InferenceResult mutable default; add registry serialization"
```

---

### Task 2: Add the inference registry schema

The results CSV needs a Polars schema that reuses the simulation join keys (`CONFIG_KEY`, `MODEL_NETWORK_KEY`) so the registries are joinable, plus the artifact/metric columns produced by `to_registry_row()`.

**Files:**
- Modify: `scripts/py/cli/schemata.py`
- Test: `tests/scripts/py/cli/test_schemata.py`

**Interfaces:**
- Consumes: `CONFIG_KEY`, `MODEL_NETWORK_KEY` (existing in `schemata.py`).
- Produces: `INFERENCE_REGISTRY_SCHEMA: pl.Schema` with columns, in order: the join keys, then `replica` (Int64), `method` (String), `runtime_seconds` (Float64), `point_estimate_path` (String), `group_estimate_path` (String), `consensus_method` (String), `log_path` (String), `fn_rate` (Float64), `fp_rate` (Float64). Column names must exactly equal the keys returned by `InferenceResult.to_registry_row()`.

- [ ] **Step 1: Write the failing test**

Create `tests/scripts/py/cli/test_schemata.py`:

```python
from datetime import timedelta
from pathlib import Path

import polars as pl

from scripts.lib.inference.inference import InferenceResult, TreeInferenceMethod
from scripts.lib.types import Polymorphism
from scripts.py.cli.schemata import INFERENCE_REGISTRY_SCHEMA


def test_registry_row_matches_schema_columns():
    row = InferenceResult(
        target_tree=1,
        ret_edges=0,
        replica=1,
        poly=Polymorphism.HIGH,
        tree_height=4,
        homoplasy_factor=0.1,
        n_chars=320,
        tree_inference_method=TreeInferenceMethod.MP,
        runtime=timedelta(seconds=1.0),
        point_estimate_path=Path("p.tree"),
    ).to_registry_row()
    # Every row key is a schema column and vice versa — a DataFrame builds cleanly.
    assert set(row.keys()) == set(INFERENCE_REGISTRY_SCHEMA.names())
    df = pl.DataFrame(data=[row], schema=INFERENCE_REGISTRY_SCHEMA)
    assert df.height == 1
    assert df.schema == INFERENCE_REGISTRY_SCHEMA
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/scripts/py/cli/test_schemata.py -v`
Expected: FAIL — `ImportError: cannot import name 'INFERENCE_REGISTRY_SCHEMA'`.

- [ ] **Step 3: Add the schema**

Append to `scripts/py/cli/schemata.py`:

```python
INFERENCE_REGISTRY_SCHEMA = pl.Schema(
    {
        **CONFIG_KEY,
        **MODEL_NETWORK_KEY,
        "replica": Int64,
        "method": String,
        "runtime_seconds": Float64,
        "point_estimate_path": String,
        "group_estimate_path": String,
        "consensus_method": String,
        "log_path": String,
        "fn_rate": Float64,
        "fp_rate": Float64,
    }
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/scripts/py/cli/test_schemata.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/py/cli/schemata.py tests/scripts/py/cli/test_schemata.py
git commit -m "feat: add INFERENCE_REGISTRY_SCHEMA joinable to simulation registry"
```

---

### Task 3: MP4 runner (command + artifact-path construction)

Pure functions that build the `runMP4.sh` argv and the paths to the artifacts it produces. Keeping these pure (no subprocess) makes them unit-testable without PAUP installed. Artifact paths come from `docs/HOW_TO_RUN.md` / `scripts/sh/runMP4.sh`: point estimate `{out}/MP4/trees/{name}-maj.tree`, tree set `{out}/MP4/trees/{name}.trees`.

**Files:**
- Create: `scripts/lib/inference/runners.py`
- Test: `tests/scripts/lib/inference/test_runners.py`

**Interfaces:**
- Consumes: `TreeInferenceMethod` from `scripts.lib.inference.inference`.
- Produces (all take/return only `str`/`Path`/`TreeInferenceMethod`, no I/O):
  - `build_argv(method, runid: str, input_csv: Path, name: str, output_dir: Path) -> list[str]`
  - `point_estimate_path(method, output_dir: Path, name: str) -> Path`
  - `group_estimate_path(method, output_dir: Path, name: str) -> Optional[Path]`
  - `consensus_method(method) -> Optional[str]`
  - `log_path(method, output_dir: Path, name: str) -> Path`
  - Each raises `NotImplementedError(f"No runner for {method}")` for methods other than `MP` (M1 scope).

- [ ] **Step 1: Write the failing test**

Create `tests/scripts/lib/inference/test_runners.py`:

```python
from pathlib import Path

import pytest

from scripts.lib.inference import runners
from scripts.lib.inference.inference import TreeInferenceMethod


def test_build_mp4_argv():
    argv = runners.build_argv(
        TreeInferenceMethod.MP,
        runid="abc123",
        input_csv=Path("data/sim_0_1_1.csv"),
        name="sim_0_1_1",
        output_dir=Path("out/high_0.1_4_320"),
    )
    assert argv == [
        "bash",
        "scripts/sh/runMP4.sh",
        "--runid",
        "abc123",
        "--input",
        "data/sim_0_1_1.csv",
        "--name",
        "sim_0_1_1",
        "--output",
        "out/high_0.1_4_320",
    ]


def test_mp4_artifact_paths():
    out = Path("out/high_0.1_4_320")
    assert runners.point_estimate_path(
        TreeInferenceMethod.MP, out, "sim_0_1_1"
    ) == out / "MP4" / "trees" / "sim_0_1_1-maj.tree"
    assert runners.group_estimate_path(
        TreeInferenceMethod.MP, out, "sim_0_1_1"
    ) == out / "MP4" / "trees" / "sim_0_1_1.trees"
    assert runners.consensus_method(TreeInferenceMethod.MP) == "majority"
    assert runners.log_path(
        TreeInferenceMethod.MP, out, "sim_0_1_1"
    ) == out / "MP4" / "logs" / "sim_0_1_1.log"


def test_unimplemented_method_raises():
    with pytest.raises(NotImplementedError):
        runners.build_argv(
            TreeInferenceMethod.GA, "x", Path("a.csv"), "a", Path("o")
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/scripts/lib/inference/test_runners.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.lib.inference.runners'`.

- [ ] **Step 3: Create the runner module**

Create `scripts/lib/inference/runners.py`:

```python
from pathlib import Path
from typing import Optional

from scripts.lib.inference.inference import TreeInferenceMethod


def build_argv(
    method: TreeInferenceMethod,
    runid: str,
    input_csv: Path,
    name: str,
    output_dir: Path,
) -> list[str]:
    if method == TreeInferenceMethod.MP:
        return [
            "bash",
            "scripts/sh/runMP4.sh",
            "--runid",
            runid,
            "--input",
            str(input_csv),
            "--name",
            name,
            "--output",
            str(output_dir),
        ]
    raise NotImplementedError(f"No runner for {method}")


def point_estimate_path(
    method: TreeInferenceMethod, output_dir: Path, name: str
) -> Path:
    if method == TreeInferenceMethod.MP:
        return output_dir / "MP4" / "trees" / f"{name}-maj.tree"
    raise NotImplementedError(f"No runner for {method}")


def group_estimate_path(
    method: TreeInferenceMethod, output_dir: Path, name: str
) -> Optional[Path]:
    if method == TreeInferenceMethod.MP:
        return output_dir / "MP4" / "trees" / f"{name}.trees"
    raise NotImplementedError(f"No runner for {method}")


def consensus_method(method: TreeInferenceMethod) -> Optional[str]:
    if method == TreeInferenceMethod.MP:
        return "majority"
    raise NotImplementedError(f"No runner for {method}")


def log_path(method: TreeInferenceMethod, output_dir: Path, name: str) -> Path:
    if method == TreeInferenceMethod.MP:
        return output_dir / "MP4" / "logs" / f"{name}.log"
    raise NotImplementedError(f"No runner for {method}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/scripts/lib/inference/test_runners.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/inference/runners.py tests/scripts/lib/inference/test_runners.py
git commit -m "feat: MP4 inference runner (argv + artifact paths)"
```

---

### Task 4: `handle_inference` orchestration

Mirror `handle_simulation`: read the simulation registry, select enabled methods, run each `(dataset, method)` pair (shelling to the runner, capturing logs, timing), and write the results registry. The output directory per condition reuses the simulation layout: `inference_data/{condition}/`, where `condition = dataset_csv.parent.name` (e.g. `high_0.1_4_320`) — derived from the path, avoiding float-formatting mismatches.

**Files:**
- Create: `scripts/py/cli/handle_inference.py`
- Test: `tests/scripts/py/cli/test_handle_inference.py`

**Interfaces:**
- Consumes: `ExperimentConfig` (from `scripts.lib.experiment`); `runners.build_argv/point_estimate_path/group_estimate_path/consensus_method/log_path` (Task 3); `InferenceResult`, `TreeInferenceMethod` (Task 1); `INFERENCE_REGISTRY_SCHEMA` (Task 2).
- Produces:
  - `select_methods(methods: MethodConfig) -> list[TreeInferenceMethod]` — returns `[TreeInferenceMethod.MP]` when `methods.mp4 is not None`, else `[]` (other methods land in M2+).
  - `handle_inference(config: ExperimentConfig) -> Path` — writes and returns the path to `inference_registry.csv`.

- [ ] **Step 1: Write the failing test**

Create `tests/scripts/py/cli/test_handle_inference.py`. It stubs `subprocess.run` (no PAUP needed) and builds a one-row simulation registry in `tmp_path`:

```python
from pathlib import Path

import polars as pl
import pytest

from scripts.lib.experiment import ExperimentConfig
from scripts.py.cli import handle_inference as hi


def _write_sim_registry(experiment_folder: Path) -> None:
    sim_dir = experiment_folder / "simulation_data"
    condition = sim_dir / "simulated_data" / "high_0.1_4_320"
    condition.mkdir(parents=True, exist_ok=True)
    dataset_csv = condition / "sim_0_1_1.csv"
    dataset_csv.write_text("id,feature,weight\n")  # contents irrelevant; runner is stubbed
    pl.DataFrame(
        {
            "poly_level": ["high"],
            "character_count": [320],
            "min_tree_height": [4],
            "homoplasy_factor": [0.1],
            "horizontal_edges": [0],
            "model_tree": [1],
            "replica": [1],
            "path": [str(dataset_csv)],
        }
    ).write_csv(sim_dir / "simulated_data_registry.csv")


def _config(experiment_folder: Path) -> ExperimentConfig:
    return ExperimentConfig.model_validate(
        {
            "experiment_folder": str(experiment_folder),
            "simulation": {
                "n_horizontal_edges": [0],
                "n_trees": 1,
                "n_replicas": 1,
                "n_taxa": 30,
                "base_config_dir": "data/base_configs",
                "base_trees_file": "data/trees.txt",
                "base_networks_dir": "data/base_networks",
                "simulation_params": [],
            },
            "methods": {"mp4": {}},
        }
    )


def test_handle_inference_writes_registry(tmp_path, monkeypatch):
    _write_sim_registry(tmp_path)
    calls = []
    monkeypatch.setattr(hi.subprocess, "run", lambda *a, **k: calls.append((a, k)))

    out = hi.handle_inference(_config(tmp_path))

    assert out == tmp_path / "inference_data" / "inference_registry.csv"
    assert len(calls) == 1  # one (dataset, method) pair
    df = pl.read_csv(out)
    assert df.height == 1
    rec = df.row(0, named=True)
    assert rec["method"] == "mp"
    assert rec["poly_level"] == "high" and rec["model_tree"] == 1
    assert rec["point_estimate_path"].endswith("MP4/trees/sim_0_1_1-maj.tree")
    assert rec["runtime_seconds"] >= 0.0


def test_select_methods_mp4_only(tmp_path):
    methods = _config(tmp_path).methods
    assert hi.select_methods(methods) == [hi.TreeInferenceMethod.MP]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/scripts/py/cli/test_handle_inference.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.py.cli.handle_inference'`.

- [ ] **Step 3: Create the orchestrator**

Create `scripts/py/cli/handle_inference.py`:

```python
import subprocess
import time
from datetime import timedelta
from pathlib import Path

import polars as pl
import shortuuid
from rich import print
from rich.progress import track

from scripts.lib.experiment import ExperimentConfig, MethodConfig
from scripts.lib.inference import runners
from scripts.lib.inference.inference import InferenceResult, TreeInferenceMethod
from scripts.lib.types import Polymorphism
from scripts.py.cli.schemata import INFERENCE_REGISTRY_SCHEMA


def select_methods(methods: MethodConfig) -> list[TreeInferenceMethod]:
    selected: list[TreeInferenceMethod] = []
    if methods.mp4 is not None:
        selected.append(TreeInferenceMethod.MP)
    # M2+: astral_3, gray_atkinson; M4: wastral, w_tree_qmc
    return selected


def handle_inference(config: ExperimentConfig) -> Path:
    sim_registry_path = (
        config.experiment_folder / "simulation_data" / "simulated_data_registry.csv"
    )
    assert sim_registry_path.is_file(), (
        f"No simulation registry at {sim_registry_path}. Run `simulation` first."
    )
    sim_registry = pl.read_csv(sim_registry_path)

    inference_dir = config.experiment_folder / "inference_data"
    inference_dir.mkdir(parents=True, exist_ok=True)

    methods = select_methods(config.methods)
    assert methods, "No supported inference methods enabled under `methods`."

    rows: list[dict[str, object]] = []
    for row in track(
        sim_registry.iter_rows(named=True),
        total=sim_registry.height,
        description="Running inference...",
    ):
        dataset_csv = Path(row["path"])
        out_dir = inference_dir / dataset_csv.parent.name
        name = dataset_csv.stem
        for method in methods:
            out_dir.mkdir(parents=True, exist_ok=True)
            argv = runners.build_argv(
                method, shortuuid.uuid(), dataset_csv, name, out_dir
            )
            log = runners.log_path(method, out_dir, name)
            log.parent.mkdir(parents=True, exist_ok=True)
            start = time.monotonic()
            with open(log, "w") as log_f:
                subprocess.run(
                    args=argv, check=True, stdout=log_f, stderr=subprocess.STDOUT
                )
            elapsed = timedelta(seconds=time.monotonic() - start)
            result = InferenceResult(
                target_tree=row["model_tree"],
                ret_edges=row["horizontal_edges"],
                replica=row["replica"],
                poly=Polymorphism(row["poly_level"]),
                tree_height=row["min_tree_height"],
                homoplasy_factor=row["homoplasy_factor"],
                n_chars=row["character_count"],
                tree_inference_method=method,
                runtime=elapsed,
                point_estimate_path=runners.point_estimate_path(method, out_dir, name),
                group_estimate_path=runners.group_estimate_path(method, out_dir, name),
                consensus_method=runners.consensus_method(method),
                log_path=log,
            )
            rows.append(result.to_registry_row())

    out_registry = inference_dir / "inference_registry.csv"
    pl.DataFrame(data=rows, schema=INFERENCE_REGISTRY_SCHEMA).write_csv(out_registry)
    print(f"Ran inference on {len(rows)} (dataset, method) pairs.")
    return out_registry
```

Note: `subprocess` is referenced via the module (`hi.subprocess`) so the test can monkeypatch it; do not `from subprocess import run`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/scripts/py/cli/test_handle_inference.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/py/cli/handle_inference.py tests/scripts/py/cli/test_handle_inference.py
git commit -m "feat: handle_inference orchestrates MP4 over the sim registry"
```

---

### Task 5: Wire the CLI command and document it

Replace the `inference` stub in `main.py` with a real call, and update the docs that describe the command as a stub.

**Files:**
- Modify: `scripts/py/cli/main.py:22-25`
- Modify: `experiments/README.md`, `docs/CLI.md`
- Test: `tests/scripts/py/cli/test_main.py`

**Interfaces:**
- Consumes: `handle_inference` (Task 4), `_get_experiment_config` (existing in `main.py`).
- Produces: `inference(config_path: Path)` Typer command that calls `handle_inference(_get_experiment_config(config_path))`.

- [ ] **Step 1: Write the failing test**

Create `tests/scripts/py/cli/test_main.py`:

```python
from pathlib import Path

from scripts.py.cli import main


def test_inference_command_invokes_handler(monkeypatch, tmp_path):
    cfg_path = tmp_path / "exp.yaml"
    cfg_path.write_text("unused")
    sentinel = object()
    monkeypatch.setattr(main, "_get_experiment_config", lambda p: sentinel)
    seen = []
    monkeypatch.setattr(main, "handle_inference", lambda c: seen.append(c))

    main.inference(cfg_path)

    assert seen == [sentinel]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/scripts/py/cli/test_main.py -v`
Expected: FAIL — `AttributeError: module 'scripts.py.cli.main' has no attribute 'handle_inference'`.

- [ ] **Step 3: Wire the command**

In `scripts/py/cli/main.py`, add the import after the existing `handle_simulation` import:

```python
from scripts.py.cli.handle_inference import handle_inference
```

Replace the stub body:

```python
@app.command()
def inference(config_path: Path):
    config = _get_experiment_config(config_path)
    handle_inference(config)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/scripts/py/cli/test_main.py -v`
Expected: 1 passed.

- [ ] **Step 5: Update docs**

In `docs/CLI.md`, replace the "`inference` is a stub" framing under the Inference section with:

```markdown
The `inference` module reads the simulation registry produced by `simulation`
and runs the methods enabled under `methods:` in the experiment YAML, writing a
joinable `inference_data/inference_registry.csv`. Currently implemented: **MP4**.

    python3 -m scripts.py.cli.main inference experiments/sample_experiment/experiment_specification.yaml
```

In `experiments/README.md`, append an `### Inference` section after `### Simulation`:

```markdown
### Inference

Reads `$experiment_folder/simulation_data/simulated_data_registry.csv` and runs
the methods enabled under `methods:`, writing artifacts and a registry under
`$experiment_folder/inference_data/`. The inference registry shares the
simulation registry's join keys, so the two can be joined for analysis.

    python3 -m scripts.py.cli.main inference experiments/sample_experiment/experiment_specification.yaml
```

- [ ] **Step 6: Run the full suite, type-check, format**

Run: `uv run python -m pytest tests/ -q && make py-static && make py-fmt`
Expected: all tests pass, ty reports no errors, ruff leaves files unchanged.

- [ ] **Step 7: Commit**

```bash
git add scripts/py/cli/main.py docs/CLI.md experiments/README.md tests/scripts/py/cli/test_main.py
git commit -m "feat: wire inference CLI command to handle_inference; document it"
```

---

## Milestones 2–5 (expand each into its own plan when reached)

These are scoped, not yet task-decomposed. Each is a separate plan because each is an independent reviewer gate and ships working software on its own.

### M2 — GA + ASTRAL3 runners
- **Deliverable:** `gray_atkinson` and `astral_3` selectable in YAML and runnable end-to-end.
- **Key files:** `scripts/lib/inference/runners.py` (add GA + ASTRAL3 argv/paths from `scripts/sh/runGA.sh`, `runASTRAL.sh`), `handle_inference.py` (`select_methods` + **method ordering**).
- **Critical constraint:** ASTRAL3 is order-dependent — `ASTRAL3Config.bipartition_strategies` of `mp4_trees`/`ga_trees` require those methods' outputs to already exist (`docs/HOW_TO_RUN.md`, "ASTRAL requires MP4 and GA first"). `select_methods` must return a topologically ordered list and `handle_inference` must run all datasets through the prerequisite methods before ASTRAL3.
- **Known defect to fix here:** `runASTRAL.sh` calls `printQuartets.py -q $QUARTET`, but the current `printQuartets.py` accepts `-i`/`-w` only (no `-q`). Reconcile before ASTRAL3 can run.

### M3 — Scoring & metrics
- **Deliverable:** `fn_rate`/`fp_rate` populated in `inference_registry.csv`.
- **Key files:** new `scripts/lib/inference/scoring.py` wrapping `scripts/R/RFScorer.R` (FN/FP = normalized RF halves; `RFScorer.R:59` `computeFnFpRate`). Resolve each row's true tree from `model_graph_registry.csv` by `(horizontal_edges, model_tree)`. Parse the `FN FP` stdout line and set the existing nullable `InferenceResult.fn_rate/fp_rate` fields.
- **Caveat:** `RFScorer.R` format/prune flags differ per method (`newick` vs `nexus`; ASTRAL-IV `q=4` prunes the extra-root leaf — see `run_inference_sim.sh:140-142`).

### M4 — wASTRAL + TREE-QMC runners
- **Deliverable:** the two methods with no existing bash runner.
- **Key files:** `runners.py` (+ argv), `experiment.py` (`WeightedASTRALConfig` is currently empty; `WeightedTreeQMCConfig.normalisation_strategy` exists with only `N2`).
- **Discovery required:** binary interfaces from `scripts/sh/installs/install_aster.sh` and `install_w_tree_qmc.sh` are not yet documented — first task of that plan is to determine their CLIs. PCH-W quartets already exist via `printQuartets.py -w` (wASTRAL weighted format).

### M5 — SLURM orchestration
- **Deliverable:** submit `(dataset, method)` jobs to SLURM instead of inline `subprocess.run`, replacing `run_parallel_sim.sh`.
- **Key files:** new `scripts/lib/inference/slurm.py` (sbatch template + submission); `handle_inference.py` gains a `--slurm` path. Encode method ordering (M2) as `--dependency=afterany` chains, mirroring `run_parallel_sim.sh:43`.
- **Reference:** `run_parallel_sim.sh` (sbatch heredoc, dependency chaining), `docs/HOW_TO_RUN.md`.

---

## Self-Review

- **Spec coverage** (`specs/cli_specs/human_specs.md`): YAML as source of truth → M1 (reuses `ExperimentConfig`). Per-method artifacts + index/registry with params, artifact paths, runtime → M1 (`InferenceResult` + `inference_registry.csv`). FN/FP metrics → M3 (fields already present, nullable). Methods MP/GA/PCH already in bash + not-yet-implemented ones → MP4 (M1), GA + ASTRAL3 (M2), wASTRAL + TREE-QMC (M4). SLURM → M5. All spec points map to a milestone.
- **Placeholder scan:** every code step shows complete code; no TBD/"handle edge cases"/"similar to". Pass.
- **Type consistency:** `to_registry_row()` keys (Task 1) ⇔ `INFERENCE_REGISTRY_SCHEMA` columns (Task 2) — asserted equal by `test_registry_row_matches_schema_columns`. `select_methods` returns `list[TreeInferenceMethod]` consumed by `handle_inference` and the runner dispatch; names match across Tasks 3–4. `build_argv`/`point_estimate_path`/`group_estimate_path`/`consensus_method`/`log_path` signatures identical in Task 3 definition and Task 4 calls. Pass.
