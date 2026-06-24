# Inference CLI/YAML Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the ad-hoc bash inference pipeline with a config-driven CLI that is a *unified entrypoint* over hardened scripts: atomic per-dataset commands (`pch infer/score/summarize`) and pipeline commands (`pch experiment inference <yaml>`) that share one Python API. Both simulated and real linguistic datasets run through the same atomic commands. Start with a fully working MP4 slice.

**Architecture — three layers, each independently testable:**

```
Typer CLI (pch infer/score/summarize, experiment …)   ← unified entrypoint; renders objects (text / --json)
        │ calls (in-process — never parses stdout)
Python API (infer/score/summarize → typed objects)    ← wraps scripts, parses their output → objects
        │ shells to
Hardened scripts (run*.sh, RFScorer.R, consensusTree.R) ← robust primitives with defined I/O contracts
```

The **Python API is the source of truth for results**: `infer() → InferenceResult`, `score() → ScoreResult`, `summarize() → Path`. The pipeline (`handle_inference`) consumes these objects directly — it does **not** shell out to the atomic CLI and parse text. The CLI commands are thin renderers: human text by default, `--json` for machine consumption. The experiment registry CSV is the durable, joinable rendering of `InferenceResult`s.

**Method configuration is unified through the existing Pydantic models** (`scripts/lib/experiment.py`: `ASTRAL3Config`, `WeightedTreeQMCConfig`, …). A `METHOD_CONFIG` registry maps each `TreeInferenceMethod` to its config class; three input paths converge on one validated instance — the experiment YAML's `methods:` block, an atomic `--method-config <yaml>`, or atomic flags (merged: flags override file override model defaults). The YAML and CLI can't drift because they validate against the same model.

**Tech Stack:** Python 3.12 (uv), Typer (CLI), Pydantic v2 (method configs + `ExperimentConfig`), Polars (registry I/O), `rich` (progress/printing), `shortuuid` (run IDs), `subprocess` (shelling to hardened scripts), pytest.

**Source spec:** `specs/cli_specs/human_specs.md`. Method descriptions: `docs/KEYS.md`. Legacy script catalogue (what inference must reproduce): `docs/HOW_TO_RUN.md`.

## Pipeline artifact model

**Everything joinable; minimal files. The registry CSV is the experiment index** — this is the difference from log-scraping.

**`inference_data/inference_registry.csv`** — one row per `(dataset, method, replica)` run. Columns: the simulation join keys (`poly_level … replica`) + `method`, `config_hash`, `fn_rate`, `fp_rate`, `runtime_seconds`, **`point_estimate_newick`** (the inferred tree inline — no per-run file), `tree_set_path`, `status`, `ran_at`. Joinable to `simulated_data_registry.csv` on the keys; ~20 MB at 50k rows (≈100 conditions × ~100 replicas × ~5 methods).

**No per-run metric/tree files** (the bloat trap). The point estimate is one Newick string → a column. Only variable/large artifacts are files, **consolidated, never per-replica**:
- `inference_data/tree_sets/{method}__{condition}.trees` — multi-tree outputs (GA posterior, MP set), grouped per method×condition (hundreds of files, not 50k).
- `inference_data/logs/` — consolidated per group, or kept only for `status=failed` runs.

**Self-contained & timestamped** — all under `experiment_folder/`:
```
experiments/my_run/
  experiment_specification.yaml      # config — source of truth
  manifest.json                      # context: created_at, completed_at, git_sha, cli_version, methods, counts, status
  simulation_data/   … simulated_data_registry.csv, configs/, model_*   (existing)
  inference_data/
    inference_registry.csv           # THE joinable index (metrics + point estimates inline)
    tree_sets/   {method}__{condition}.trees
    logs/
    .parts/      {run_key}.json       # transient per-run staging (see below); cleared after compaction
```
`manifest.json` carries experiment-level context; per-row `ran_at` records when each run was computed.

**Concurrency-safe idempotent writes (SLURM 4h reruns).** Jobs time out and rerun, often in parallel — so no shared-file writes. Each run writes only its own `.parts/{run_key}.json` (idempotent: a killed job's partial part is replaced on rerun). `pch experiment compact` merges parts → the canonical registry (last-writer-wins by `run_key`, newest `ran_at`) and concatenates tree-set parts into the group files. **No two jobs write the same file → no mutex needed** — more robust than `flock` on a shared NFS/Lustre FS. The local executor compacts at the end; SLURM runs `compact` as a final dependent job (and `pch experiment status` compacts on demand).

**CLI interacts with artifacts** (the payoff of joinability):
- `pch experiment status <folder>` — counts by method, % complete, failures, run timestamps.
- `pch experiment query <folder> [filters] [--json]` — filter + join sim⨝inference registries; answers "FN/FP for ASTRAL3 across high-poly conditions" with zero log scraping.
- `pch experiment get <folder> --run <key> --what point_estimate|tree_set|log`.

## Global Constraints

- **Python 3.12, managed with uv.** Run tests with `uv run python -m pytest`, type-check with `make py-static` (ty), format with `make py-fmt` (ruff), lint with `make py-lint`.
- **Tests mirror `scripts/` under `tests/`** (e.g. `scripts/lib/inference/inference.py` → `tests/scripts/lib/inference/test_inference.py`). No `__init__.py` needed — the project uses implicit namespace packages (confirmed: `scripts/py/cli/` and `scripts/lib/inference/` have none).
- **Registry join keys must match the simulation registry verbatim** (`scripts/py/cli/schemata.py`): `poly_level, character_count, min_tree_height, homoplasy_factor, horizontal_edges, model_tree, replica` — so inference rows join to simulation rows (`docs/KEYS.md`).
- **The Python API returns objects; everything else renders them.** `score()` returns a `ScoreResult`, not a printed line; `infer()` returns an `InferenceResult`. stdout (text / `--json`) and the registry CSV are renderings. The pipeline calls the API in-process and **never parses CLI stdout**.
- **Method config flows through the existing Pydantic models** — never re-define a method's parameters outside its config class. Atomic flags and `--method-config` both produce a validated instance of that class.
- **Wrap, don't reimplement; harden first.** Keep PAUP/MrBayes/ASTRAL/R orchestration in the existing scripts; the API shells to them. Each script gets a defined I/O contract (M0) before the API depends on it — a subprocess+parse is hidden inside an API function so nothing downstream sees raw text.
- **Everything joinable, minimal files** (see *Pipeline artifact model*): one registry row per run, point estimate inline, no per-replica metric/tree files; heavy artifacts consolidated per method×condition.
- **Concurrency-safe & idempotent.** Runs write only their own `.parts/{run_key}.json`; `compact` merges. No shared-file writes, no locks. Reruns (SLURM timeouts) overwrite by `run_key` — safe to run any number of times.
- **Experiments self-contained & contextualised.** All artifacts under `experiment_folder/`; `manifest.json` timestamps the run (`created_at`/`completed_at`, git sha, CLI version).
- **Brevity (repo CLAUDE.md):** keep code, comments, and docs tight — if removing a word loses nothing, remove it.
- **`ruff` ignores `E741`** (see `pyproject.toml`); otherwise default rules.

---

## Migration Roadmap (what needs doing, end to end)

The full migration is too large for one placeholder-free plan, so it is split into milestones. **Each milestone produces working, testable software on its own.** This document specifies **M0** (script contracts) and **M1** (the three-layer scaffolding) in detail; M2–M5 are scoped at the interface level and expand into their own plans when reached.

> **Architecture note:** the original M1 below was written before the three-layer (CLI → Python API → hardened scripts) decision. Its component tasks remain valid building blocks — Task 1 (`InferenceResult`), Task 2 (registry schema), Task 3 (MP4 command/path construction, now the hardened-script *wrapper*). The decision **inserts** two tasks and **reshapes** two; see *"M1 task structure (three-layer)"* below for the authoritative task list and interface signatures. Full TDD step-by-step for the new/changed tasks is written at execution time (or after design lock).

| Milestone | Deliverable | Status |
|-----------|-------------|--------|
| **M0 — Script hardening & interface contracts** | Pin a defined I/O contract (exact inputs, outputs, stdout shape, exit codes) for each `run*.sh` and `*.R` the API will call; fix the stale `printQuartets.py` interface; remove hardcoded `~/scratch` assumptions so the Python API can call them reliably. No Python yet — robust primitives only. | **Detailed below** |
| **M1 — API + atomic `infer` + MP4 + pipeline slice** | The three-layer scaffolding: `infer() → InferenceResult` API wrapping the hardened MP4 script, the `METHOD_CONFIG` registry + `resolve_config`, the atomic `pch infer --method mp4`, and `pch experiment inference <yaml>` running MP4 across the sim registry. Implements the artifact model: per-run `.parts/` writes → `compact` → joinable `inference_registry.csv` (point estimate inline), `manifest.json`, and `pch experiment status`. | **Detailed below** |
| **M2 — Atomic `score` + `summarize` (object API)** | `score() → ScoreResult` (wraps `RFScorer.R`) and `summarize() → Path` (wraps `consensusTree.R`), each with a thin `pch score`/`pch summarize` CLI (text + `--json`). The true tree for scoring resolves from `model_graph_registry.csv` by `(horizontal_edges, model_tree)`; the pipeline populates `fn_rate`/`fp_rate` by calling `score()` in-process. | Scoped below |
| **M3 — GA + ASTRAL3 runners** | Add Gray-Atkinson and ASTRAL III via `infer()`, with `ASTRAL3Config` (bipartition strategies) and `GAConfig` flowing through `resolve_config`. ASTRAL3 is order-dependent — `mp4_trees`/`ga_trees` strategies require MP4/GA outputs to exist first (`docs/HOW_TO_RUN.md`); the pipeline sequences methods accordingly. | Scoped below |
| **M4 — wASTRAL + TREE-QMC** | The two methods with no existing bash runner — first discover/harden (M0-style) the binary interfaces from `install_aster.sh` / `install_w_tree_qmc.sh`, then wire `WeightedASTRALConfig` / `WeightedTreeQMCConfig`. PCH-W quartets already exist (`printQuartets.py -w`). | Scoped below |
| **M5 — Pipeline executor + SLURM** | `pch experiment inference --executor local\|slurm [--dry-run]` via a `LocalExecutor`/`SlurmExecutor` abstraction; SLURM emits one sbatch per `(dataset, method)` (each calling `pch infer`) with `--dependency` chains for order-dependent methods, replacing `run_parallel_sim.sh`. Real-dataset atomic runs already work (path-based `pch infer`, no registry). | Scoped below |

---

## M0 — Script hardening & interface contracts (detail)

No Python. For each script the API will call, write down and enforce a contract, then fix the known gaps. Deliverable: a short `docs/SCRIPT_CONTRACTS.md` table + the script edits, with a smoke test per script.

- **`scripts/sh/runMP4.sh`** — contract: in `--input <csv> --name --output <dir>`; out `{out}/MP4/trees/{name}-maj.tree` (point estimate), `{name}.trees` (set), `{out}/MP4/logs/{name}.log`; exit non-zero on PAUP failure. Edit: make the scratch dir configurable (env `PCH_SCRATCH`, default `~/scratch`) instead of hardcoded; `mkdir -p` it.
- **`scripts/sh/runGA.sh`, `runASTRAL.sh`** — same treatment (contracts + scratch). `runASTRAL.sh`: **fix the stale `printQuartets.py -q` call** — current `printQuartets.py` takes `-i`/`-w`, no `-q`; reconcile the quartet-generation interface so the script runs.
- **`scripts/R/RFScorer.R`** — contract: stdout is **exactly one line** `fn_rate fp_rate` (space-separated floats), nothing else; all progress/diagnostics to stderr; exit non-zero on bad input. (Today it already `cat`s `fn fp`, but `--do-print` can leak to stdout — gate it to stderr so `score()` can parse unambiguously.)
- **`scripts/R/consensusTree.R`** — contract: in `-i <trees> -m <mode> -o <out>`; writes one Newick tree to `-o`; exit non-zero if input unreadable.

## File Structure (Milestone 1, three-layer)

- **Modify** `scripts/lib/inference/inference.py` — fix the `metadata` mutable-default crash; add breadcrumb fields + `to_registry_row()`. *(existing Task 1)*
- **Modify** `scripts/py/cli/schemata.py` — add `INFERENCE_REGISTRY_SCHEMA`. *(existing Task 2)*
- **Create** `scripts/lib/inference/runners.py` — pure per-method argv + artifact-path construction over the hardened scripts (MP4 in M1). *(existing Task 3)*
- **Create** `scripts/lib/inference/methods.py` — **NEW:** `METHOD_CONFIG` registry (method → Pydantic config class) + `resolve_config(method, config_file, overrides) -> BaseModel`.
- **Create** `scripts/lib/inference/api.py` — **NEW:** `infer(...) -> InferenceResult` — the object-returning API; builds argv via `runners`, runs the hardened script, times it, assembles the result. The single point that touches `subprocess`.
- **Modify** `scripts/py/cli/handle_inference.py` — pipeline: iterate the sim registry, call `api.infer(...)` per `(dataset, method)`, write the registry. *(reshaped Task 4 — calls the API, no longer shells directly)*
- **Modify** `scripts/py/cli/main.py` — wire **both** `pch infer` (atomic, renders `InferenceResult`; `--json`) and `pch experiment inference` (pipeline). *(reshaped Task 5)*
- **Modify** `experiments/README.md`, `docs/CLI.md` — document the atomic + pipeline commands.
- **Create** tests mirroring each module under `tests/`, incl. `test_methods.py` (config resolution) and `test_api.py` (stubbed subprocess → `InferenceResult`).

### M1 task structure (three-layer) — authoritative list

| # | Task | Status vs original | Key interface |
|---|------|--------------------|---------------|
| 1 | Fix `InferenceResult` + `to_registry_row()` | unchanged (detailed below) | `InferenceResult.to_registry_row() -> dict` |
| 2 | `INFERENCE_REGISTRY_SCHEMA` | unchanged (detailed below) | Polars schema matching the row dict |
| 3 | MP4 `runners.py` (argv + paths) | unchanged (detailed below) | `build_argv(method, runid, input_csv, name, out) -> list[str]` |
| 4 | **NEW** `methods.py` config registry | new | `resolve_config(method: TreeInferenceMethod, config_file: Path\|None, overrides: dict) -> BaseModel`; `METHOD_CONFIG: dict[TreeInferenceMethod, type[BaseModel]]` |
| 5 | **NEW** `api.infer()` | new | `infer(input_csv: Path, output_dir: Path, method: TreeInferenceMethod, config: BaseModel, *, name: str\|None=None) -> InferenceResult` |
| 6 | `handle_inference` pipeline | reshaped (was Task 4) | `handle_inference(config: ExperimentConfig) -> Path`; loops registry, calls `api.infer`, writes CSV |
| 7 | Wire `pch infer` + `pch experiment inference` | reshaped (was Task 5) | atomic command renders `InferenceResult` (text/`--json`); pipeline command calls `handle_inference` |

The full TDD steps for Tasks 1–3 follow verbatim below (still valid). Tasks 4–7 are specified at the interface level above and get their TDD steps written when M1 executes.

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

### Task 4 (SUPERSEDED → new Tasks 6–7): `handle_inference` orchestration

> **Superseded by the three-layer decision.** This version shells from `handle_inference` directly to the runner. Under the new architecture the subprocess call moves into `api.infer()` (new Task 5 in the authoritative list), and `handle_inference` calls `api.infer(...)` per pair (Task 6). The code below is retained as reference for the registry-writing loop and the `condition = dataset_csv.parent.name` path trick — both still apply — but the subprocess/timing block migrates into `api.infer()`.

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

> **Superseded by the three-layer decision (→ new Task 7).** This version wires only the pipeline `inference` command. The new Task 7 wires **both** the atomic `pch infer` (renders an `InferenceResult`; `--json`) **and** `pch experiment inference` (pipeline). The stub-replacement and doc-update steps below still apply to the pipeline command.

Replace the `inference` stub in `main.py` with a real call, and update the docs that describe the command as a stub.

**Files:**
- Modify: `scripts/py/cli/main.py` (the `inference` stub)
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

Scoped, not yet task-decomposed; each becomes its own plan and reviewer gate when reached.

### M2 — Atomic `score` + `summarize` (object API)
- **Deliverable:** `score() → ScoreResult` and `summarize() → Path`, each with a thin `pch score` / `pch summarize` CLI (text + `--json`); pipeline populates `fn_rate`/`fp_rate` by calling `score()` in-process.
- **Key files:** new `scripts/lib/inference/scoring.py` — `ScoreResult` dataclass + `score(estimate, reference, *, fmt, prune) -> ScoreResult` wrapping the hardened `RFScorer.R` (parses its one-line `fn fp` stdout, M0 contract); `summarize.py` wrapping `consensusTree.R`. `api.infer` / `handle_inference` gain the scoring call; true tree resolves from `model_graph_registry.csv` by `(horizontal_edges, model_tree)`.
- **Caveat:** `RFScorer.R` format/prune flags differ per method (`newick` vs `nexus`; ASTRAL-IV `q=4` prunes the extra-root leaf — see `run_inference_sim.sh`). `score()` exposes these as params.

### M3 — GA + ASTRAL3 runners
- **Deliverable:** `gray_atkinson` and `astral_3` runnable via `pch infer` and the pipeline.
- **Key files:** `runners.py` (GA + ASTRAL3 argv/paths over the hardened `runGA.sh`/`runASTRAL.sh`); `methods.py` already routes `ASTRAL3Config`/`GAConfig` through `resolve_config` — wire the flags (`--exact`, repeatable `--bipartition`); `handle_inference` gains **method ordering**.
- **Critical constraint:** ASTRAL3 is order-dependent — `ASTRAL3Config.bipartition_strategies` of `mp4_trees`/`ga_trees` require those methods' outputs to already exist (`docs/HOW_TO_RUN.md`). The pipeline must run all datasets through prerequisite methods before ASTRAL3. (The stale `printQuartets.py` interface is already fixed in M0.)

### M4 — wASTRAL + TREE-QMC
- **Deliverable:** the two methods with no existing bash runner, via `pch infer`.
- **Key files:** new hardened runner scripts (M0-style) + `runners.py` argv; `methods.py`/`experiment.py` (`WeightedASTRALConfig` is currently empty; `WeightedTreeQMCConfig.normalisation_strategy` has only `N2` — extend as the binary supports). Flags: `--normalisation n2`, etc.
- **Discovery required:** binary interfaces from `install_aster.sh` / `install_w_tree_qmc.sh` are undocumented — first task is to determine and contract their CLIs. PCH-W quartets already exist via `printQuartets.py -w`.

### M5 — Pipeline executor + SLURM
- **Deliverable:** `pch experiment inference --executor local|slurm [--dry-run]`, replacing `run_parallel_sim.sh`. Real-dataset atomic runs already work (path-based `pch infer`).
- **Key files:** new `scripts/lib/inference/executor.py` — `LocalExecutor` (inline `api.infer`) / `SlurmExecutor` (one sbatch per `(dataset, method)`, each invoking `pch infer`, with `--dependency=afterany` chains for ordered methods). `handle_inference` takes an executor.
- **Reference:** `run_parallel_sim.sh` (sbatch heredoc, dependency chaining), `docs/HOW_TO_RUN.md`.

---

## Documentation — the run manual

A single living manual, **`docs/RUNNING_INFERENCE.md`**, is the entry point for *running* the pipeline, written for two audiences in one document:

- **Humans** — a task-oriented walkthrough: install/setup, "run an experiment end to end" with copy-paste commands, the `experiment_folder/` layout, how to read `inference_registry.csv`, how to query results, and how reruns/SLURM behave. Concrete examples over prose.
- **Agents** — a precise reference block that lets an agent operate without reading source: exact command signatures (`pch infer/score/summarize`, `pch experiment inference/status/query/get/compact`), the registry column contract + join keys, the invariants (objects-not-stdout, idempotent `.parts`→`compact`, self-contained folder), and where each artifact lives. Each fact links to its canonical doc (`docs/KEYS.md` keys, `docs/SCRIPT_CONTRACTS.md` script I/O, `docs/CLI.md` command surface).

**How the docs fit together** (no duplication — each owns one thing):

| Doc | Owns |
|---|---|
| `docs/RUNNING_INFERENCE.md` | **NEW** — how to *run* it (humans + agents); links the rest |
| `docs/CLI.md` | command surface reference (flags, args) |
| `docs/KEYS.md` | join keys + method descriptions |
| `docs/SCRIPT_CONTRACTS.md` | **NEW (M0)** — each script's I/O contract |
| `docs/HOW_TO_RUN.md` | legacy bash catalogue (migration reference; retired when migration completes) |
| `CLAUDE.md` `## Docs` index | one-line pointer to each of the above |

**Docs are a per-milestone deliverable, not a final phase.** Each milestone's Definition of Done includes updating `RUNNING_INFERENCE.md` (and the relevant reference doc) for what it shipped, and adding its entry to the `CLAUDE.md` index — so the manual is never stale. M0 creates `SCRIPT_CONTRACTS.md`; M1 creates `RUNNING_INFERENCE.md` covering `infer` + `experiment inference`/`status`; later milestones extend it.

---

## Self-Review

- **Spec coverage** (`specs/cli_specs/human_specs.md`): YAML as source of truth → M1 (reuses `ExperimentConfig` + `METHOD_CONFIG`). Per-method config via Pydantic models, flags, or `--method-config` → M1 (`resolve_config`). Per-method artifacts + index/registry → M1 (`InferenceResult` + `inference_registry.csv`). FN/FP metrics as objects/stdout/CSV → M2 (`ScoreResult`, `score()`). Methods → MP4 (M1), GA + ASTRAL3 (M3), wASTRAL + TREE-QMC (M4). Atomic single commands on real *and* simulated data → M1 (`pch infer`, path-based). SLURM + local executor → M5. Script robustness → M0. **Joinable artifacts + no per-replica bloat, self-contained & timestamped folder, concurrency-safe reruns, CLI query** → *Pipeline artifact model* (registry/parts/compact/manifest in M1; `query`/`get` join in M2+). **Run manual for humans + agents** → *Documentation* (per-milestone). All spec points map to a milestone.
- **Placeholder scan:** M0 + Tasks 1–3 fully specified (code below); Tasks 4–7 and M2–M5 specified at the interface level (signatures given) pending execution/design-lock — flagged explicitly, not silent TBDs.
- **Type consistency:** `to_registry_row()` keys (Task 1) ⇔ `INFERENCE_REGISTRY_SCHEMA` columns (Task 2) — asserted equal by `test_registry_row_matches_schema_columns`. New layer: `resolve_config(...) -> BaseModel` (Task 4) feeds `api.infer(..., config: BaseModel) -> InferenceResult` (Task 5), consumed by `handle_inference` (Task 6) and rendered by `pch infer`/`pch experiment inference` (Task 7). `build_argv(...)` (Task 3) is called inside `api.infer`. `ScoreResult` (M2) is the return of `score()`, rendered to stdout/CSV — never parsed back.
