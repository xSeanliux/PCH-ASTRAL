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

**Method configuration is unified through the existing Pydantic models** (`scripts/lib/experiment.py`: `ASTRAL3Config`, `WeightedTreeQMCConfig`, …). A `METHOD_CONFIG` registry maps each `TreeInferenceMethod` to its config class; **two** input paths converge on one validated instance — the experiment YAML's `methods:` block, or an atomic `--method-config <yaml>` (file values over model defaults). **No per-method CLI flags** — they're fiddly and every method would need its own set; a small YAML is simpler and the same file works for atomic and pipeline runs. The two paths can't drift because they validate against the same model.

**Tech Stack:** Python 3.12 (uv), Typer (CLI), Pydantic v2 (method configs + `ExperimentConfig`), Polars (registry I/O), `rich` (progress/printing), `shortuuid` (run IDs), `subprocess` (shelling to binaries/R), pytest. M5 adds `submitit` for SLURM.

**Source spec:** `specs/cli_specs/human_specs.md`. Method descriptions: `docs/KEYS.md`. Legacy script catalogue (what inference must reproduce): `docs/HOW_TO_RUN.md`.

## Pipeline artifact model

**Everything joinable; minimal files. The registry CSV is the experiment index** — this is the difference from log-scraping.

**`inference_data/inference_registry.csv`** — one row per run. A run is keyed by **`run_key` = the full dataset join keys (`poly_level, character_count, min_tree_height, homoplasy_factor, horizontal_edges, model_tree, replica`) + `method` + `config_hash`**. The dataset explodes over its keys (one per condition×replica×graph); the `config_hash` term means the *same* dataset+method run under two different sub-configs (e.g. ASTRAL3 with `mp4_trees` vs `ga_trees`; TREE-QMC `n0` vs `n2`) are **distinct rows that don't overwrite each other**. Columns: the join keys + `method` + `config_hash` + **`method_config_json`** (the Pydantic config serialized, so sub-configs are queryable, not just hashed) + `fn_rate`, `fp_rate`, `runtime_seconds`, **`point_estimate_newick`** (the inferred tree inline — no per-run file), `tree_set_path`, `status`, `ran_at`. Joinable to `simulated_data_registry.csv` on the dataset keys; ~20 MB at tens of thousands of rows.

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

**Concurrency-safe idempotent writes (SLURM 4h reruns).** Jobs time out and rerun, often in parallel. Each run writes its own `.parts/{run_key}.json`. Two *different* runs never share a path. But two runs of the **same** `(dataset, method, config)` can be launched at once (double-submit, or a requeue overlapping the original) — so don't assume uniqueness; make the write **atomic instead**: write to a per-process temp `.parts/{run_key}.{pid}.{uuid}.tmp`, then `os.replace()` onto `{run_key}.json`. POSIX rename is atomic on a single filesystem, so a concurrent duplicate just produces a second complete temp and a second atomic rename — last writer wins, the target is **never torn or half-written**, no `flock` (unreliable over NFS/Lustre) needed. `pch experiment compact` merges parts → the canonical registry (last-writer-wins by `run_key`, newest `ran_at`) and concatenates tree-set parts. The local executor compacts at the end; SLURM runs `compact` as a final dependent job. **This atomic-rename merge is the riskiest logic — it gets the most unit tests** (see *Validation*).

**CLI interacts with artifacts — minimal first.** Only two commands are actually necessary:
- `pch experiment compact <folder>` — merge `.parts` → registry (required; nothing works without it).
- `pch experiment status <folder>` — counts by method, % complete, failures, timestamps (the rerun loop needs "what's left?").

`query` and `get` are **deferred (YAGNI)** — the registry is a plain joinable CSV, so `pl.read_csv(...).join(...)` covers ad-hoc analysis until a command earns its place. Add them only when the same query gets typed repeatedly.

## Global Constraints

- **Python 3.12, managed with uv.** Run tests with `uv run python -m pytest`, type-check with `make py-static` (ty), format with `make py-fmt` (ruff), lint with `make py-lint`.
- **Tests mirror `scripts/` under `tests/`** (e.g. `scripts/lib/inference/inference.py` → `tests/scripts/lib/inference/test_inference.py`). No `__init__.py` needed — the project uses implicit namespace packages (confirmed: `scripts/py/cli/` and `scripts/lib/inference/` have none).
- **Registry join keys must match the simulation registry verbatim** (`scripts/py/cli/schemata.py`): `poly_level, character_count, min_tree_height, homoplasy_factor, horizontal_edges, model_tree, replica` — so inference rows join to simulation rows (`docs/KEYS.md`).
- **The Python API returns objects; everything else renders them.** `score()` returns a `ScoreResult`, not a printed line; `infer()` returns an `InferenceResult`. stdout (text / `--json`) and the registry CSV are renderings. The pipeline calls the API in-process and **never parses CLI stdout**.
- **Method config flows through the existing Pydantic models** — never re-define a method's parameters outside its config class. Both the experiment YAML's `methods:` block and atomic `--method-config <yaml>` produce a validated instance of that class. No per-method CLI flags.
- **Wrap, don't reimplement; harden first.** Keep PAUP/MrBayes/ASTRAL/R orchestration in the existing scripts; the API shells to them. Each script gets a defined I/O contract (M0) before the API depends on it.
- **The *Pipeline artifact model* above is a hard constraint:** everything joinable, minimal files, concurrency-safe `.parts`→`compact` reruns, self-contained timestamped `experiment_folder/`.
- **Brevity (repo CLAUDE.md):** keep code, comments, and docs tight — if removing a word loses nothing, remove it.
- **`ruff` ignores `E741`** (see `pyproject.toml`); otherwise default rules.

---

## Migration Roadmap (what needs doing, end to end)

The full migration is too large for one placeholder-free plan, so it is split into milestones. **Each milestone produces working, testable software on its own.** This document specifies **M0** (script contracts) and **M1** (the three-layer scaffolding) in detail; M2–M5 are scoped at the interface level and expand into their own plans when reached.

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

For each step the API will call, **rigorously specify a contract and make it testable** (a smoke test asserts it). Deliverable: `docs/SCRIPT_CONTRACTS.md` (one row per primitive: command, inputs, outputs, stdout/stderr shape, exit codes) + the edits + smoke tests.

**Decision per primitive — keep the `.sh` wrapper, or call the binary/R directly?** The bash runners bundle orchestration (e.g. `runMP4.sh` = R nexus-gen → PAUP → R consensus). Default preference: **the Python API orchestrates and shells out only to the actual binary/R command** (PAUP, MrBayes, ASTRAL jar, `Rscript`), retiring the `.sh` wrappers where they only sequence steps — fewer layers, each step independently testable. Keep a `.sh` wrapper only where it earns its keep (genuinely complex shell glue). M0 records this choice per primitive in the contracts doc; `runners.py` (Task 3) then targets whichever the contract names.

Primitives to contract:
- **MP4** (R nexus-gen `commandLineNex.R` → PAUP → R consensus `consensusTree.R`): inputs `csv, name, out_dir`; outputs `{out}/MP4/trees/{name}-maj.tree` (point estimate), `{name}.trees` (set), log; non-zero exit on PAUP failure. Make the scratch dir configurable (env `PCH_SCRATCH`, default `~/scratch`); `mkdir -p`.
- **GA** (`commandLineNex.R` → MrBayes → R MCC consensus) and **ASTRAL** (`printQuartets.py` → `getResultBipartitions.py` → ASTRAL jar) — same treatment. **Fix the stale `printQuartets.py -q` call** (current script takes `-i`/`-w`, no `-q`).
- **`RFScorer.R`** — stdout is **exactly one line** `fn_rate fp_rate` (space-separated floats), nothing else; progress/diagnostics to stderr; non-zero exit on bad input. (Today `--do-print` can leak to stdout — gate it to stderr so `score()` parses unambiguously.)
- **`consensusTree.R`** — in `-i <trees> -m <mode> -o <out>`; writes one Newick tree to `-o`; non-zero exit if input unreadable.

## File Structure (Milestone 1, three-layer)

- **Modify** `scripts/lib/inference/inference.py` — fix the `metadata` mutable-default crash; add breadcrumb fields + `to_registry_row()`. *(Task 1)*
- **Modify** `scripts/py/cli/schemata.py` — add `INFERENCE_REGISTRY_SCHEMA`. *(Task 2)*
- **Create** `scripts/lib/inference/runners.py` — pure per-method argv + artifact-path construction over the hardened scripts (MP4 in M1). *(Task 3)*
- **Create** `scripts/lib/inference/methods.py` — `METHOD_CONFIG` registry (method → Pydantic config class) + `resolve_config(method, config_file) -> BaseModel` (validates the YAML, or returns the model's defaults when `config_file is None`). *(Task 4)*
- **Create** `scripts/lib/inference/api.py` — `infer(...) -> InferenceResult`: builds argv via `runners`, runs the hardened script, times it, assembles the result. The single point that touches `subprocess`. *(Task 5)*
- **Modify** `scripts/py/cli/handle_inference.py` — pipeline: iterate the sim registry, call `api.infer(...)` per `(dataset, method)`, write `.parts`, compact. *(Task 6)*
- **Modify** `scripts/py/cli/main.py` — wire **both** `pch infer` (atomic, renders `InferenceResult`; `--json`) and `pch experiment inference` (pipeline). *(Task 7)*
- **Modify** `experiments/README.md`, `docs/CLI.md` — document the atomic + pipeline commands.
- **Create** tests mirroring each module under `tests/`, incl. `test_methods.py` (config resolution) and `test_api.py` (stubbed subprocess → `InferenceResult`).

### M1 task structure (three-layer) — authoritative list

| # | Task | Detail | Key interface |
|---|------|--------|---------------|
| 1 | Fix `InferenceResult` + `to_registry_row()` | full TDD below | `InferenceResult.to_registry_row() -> dict` |
| 2 | `INFERENCE_REGISTRY_SCHEMA` | full TDD below | Polars schema matching the row dict |
| 3 | MP4 `runners.py` (argv + paths) | full TDD below | `build_argv(method, runid, input_csv, name, out) -> list[str]` |
| 4 | `methods.py` config registry | TDD at execution | `resolve_config(method: TreeInferenceMethod, config_file: Path\|None) -> BaseModel`; `METHOD_CONFIG: dict[TreeInferenceMethod, type[BaseModel]]` |
| 5 | `api.infer()` | TDD at execution | `infer(input_csv: Path, output_dir: Path, method: TreeInferenceMethod, config: BaseModel, *, name: str\|None=None) -> InferenceResult` |
| 6 | `handle_inference` pipeline | TDD at execution | `handle_inference(config: ExperimentConfig) -> Path`; loops registry, calls `api.infer`, writes `.parts`, compacts |
| 7 | Wire `pch infer` + `pch experiment inference` | TDD at execution | atomic command renders `InferenceResult` (text/`--json`); pipeline command calls `handle_inference` |

Tasks 1–3 have full TDD steps below. Tasks 4–7 are specified at the interface level above; their TDD steps are written when M1 executes. Carry-over gotchas for Tasks 4–7:
- **Condition dir** = `dataset_csv.parent.name` (e.g. `high_0.1_4_320`) — derive from the path, not by reformatting floats.
- **`subprocess` lives only in `api.infer`** (Task 5); reference it via the module so tests can monkeypatch. `handle_inference` (Task 6) writes each result to `.parts/{run_key}.json` then `compact`s — it does **not** write the registry row-by-row (artifact model).
- **`select_methods(MethodConfig) -> [TreeInferenceMethod.MP]`** for M1 (only `mp4` wired).

---

### Task 1: Fix `InferenceResult` and add registry serialization

The dataclass currently crashes on import: `metadata: dict[str, str] = {}` raises `ValueError: mutable default <class 'dict'> for field metadata is not allowed`. Fix it, add the breadcrumb fields the spec asks for (log path, FN/FP metrics — nullable, populated in M2), and a method that converts a result into a registry row keyed to match the simulation registry.

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

    # metrics, populated by the scoring milestone (M2)
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

> Note: when Task 5 (`api.infer`) lands the artifact model, this schema gains `config_hash`, `point_estimate_newick`, `tree_set_path`, `status`, `ran_at` and drops the per-run `*_path` columns that become inline/consolidated. Extend the test in lockstep.

---

### Task 3: MP4 runner (command + artifact-path construction)

Pure functions that build the MP4 command argv and the paths to the artifacts it produces. Keeping these pure (no subprocess) makes them unit-testable without PAUP installed. The argv below targets `bash scripts/sh/runMP4.sh` as the v1; if M0 decides MP4 orchestrates in Python (R nexus → PAUP → R consensus called directly), `build_argv` instead returns the binary/R command per the M0 contract — the test changes with it. Artifact paths (M0 contract): point estimate `{out}/MP4/trees/{name}-maj.tree`, tree set `{out}/MP4/trees/{name}.trees`.

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

## Milestones 2–5 (expand each into its own plan when reached)

Scoped, not yet task-decomposed; each becomes its own plan and reviewer gate when reached.

### M2 — Atomic `score` + `summarize` (object API)
- **Deliverable:** `score() → ScoreResult` and `summarize() → Path`, each with a thin `pch score` / `pch summarize` CLI (text + `--json`); pipeline populates `fn_rate`/`fp_rate` by calling `score()` in-process.
- **Key files:** new `scripts/lib/inference/scoring.py` — `ScoreResult` dataclass + `score(estimate, reference, *, fmt, prune) -> ScoreResult` wrapping the hardened `RFScorer.R` (parses its one-line `fn fp` stdout, M0 contract); `summarize.py` wrapping `consensusTree.R`. `api.infer` / `handle_inference` gain the scoring call; true tree resolves from `model_graph_registry.csv` by `(horizontal_edges, model_tree)`.
- **Caveat:** `RFScorer.R` format/prune flags differ per method (`newick` vs `nexus`; ASTRAL-IV `q=4` prunes the extra-root leaf — see `run_inference_sim.sh`). `score()` exposes these as params.

### M3 — GA + ASTRAL3 runners
- **Deliverable:** `gray_atkinson` and `astral_3` runnable via `pch infer` and the pipeline.
- **Key files:** `runners.py` (GA + ASTRAL3 argv/paths over the hardened `runGA.sh`/`runASTRAL.sh` or direct binary/R calls per M0); `methods.py` already routes `ASTRAL3Config`/`GAConfig` through `resolve_config` (config comes from the YAML/`--method-config`, no flags); `handle_inference` gains **method ordering**.
- **Critical constraint — order dependency.** ASTRAL3's `mp4_trees`/`ga_trees` bipartition strategies need MP4/GA outputs to exist first (`docs/HOW_TO_RUN.md`). Handle it with the **simplest thing that works: a check** — `infer(astral3)` verifies the prerequisite point estimates exist and fails fast with a clear message if not. The pipeline orders methods so prerequisites run first; under SLURM (M5) this becomes a `--dependency` chain as an optimization, not a correctness requirement. (The stale `printQuartets.py` interface is already fixed in M0.)

### M4 — wASTRAL + TREE-QMC
- **Deliverable:** the two methods with no existing bash runner, via `pch infer`.
- **Key files:** new hardened runners (M0-style) + `runners.py` argv; `methods.py`/`experiment.py` (`WeightedASTRALConfig` is currently empty; `WeightedTreeQMCConfig.normalisation_strategy` has only `N2` — extend the Pydantic model as the binary supports; config comes via YAML).
- **Discovery required:** binary interfaces from `install_aster.sh` / `install_w_tree_qmc.sh` are undocumented — first task is to determine and contract their CLIs. PCH-W quartets already exist via `printQuartets.py -w`.

### M5 — Pipeline executor + SLURM
- **Deliverable:** `pch experiment inference --executor local|slurm [--dry-run]`, replacing `run_parallel_sim.sh`. Real-dataset atomic runs already work (path-based `pch infer`).
- **Approach — use [`submitit`](https://github.com/facebookincubator/submitit), don't hand-roll.** submitit submits Python callables as SLURM jobs and already handles **job arrays, `afterok` dependencies, and requeue-on-timeout** — the last is exactly the 4h-cap rerun scenario (a preempted/timed-out job auto-resubmits, and our idempotent `.parts` write makes that safe). Hand-rolling jinja sbatch templates + `sacct` polling would reimplement this; submitit is the lazy-correct choice. It's a new dependency, but replicating arrays + dependency chains + requeue is not "a few lines."
- **Key files:** new `scripts/lib/inference/executor.py` — `LocalExecutor` (inline `api.infer`) and `SlurmExecutor` (a `submitit.AutoExecutor` mapping each `(dataset, method, config)` run to `api.infer`; method ordering via submitit dependencies). `handle_inference` takes an executor; the run body is the same `api.infer` either way.
- **Fallback** if submitit doesn't fit the cluster: jinja-templated sbatch per run calling `pch infer`, modeled on `run_parallel_sim.sh` (sbatch heredoc + `--dependency=afterany`, `docs/HOW_TO_RUN.md`).

---

## Documentation — the run manual

A single living manual, **`docs/RUNNING_INFERENCE.md`**, is the entry point for *running* the pipeline, for two audiences:

- **Humans** — task-oriented walkthrough: setup, "run an experiment end to end" with copy-paste commands, the `experiment_folder/` layout, how to read/query `inference_registry.csv`, how reruns/SLURM behave.
- **Agents** — a precise reference: exact command signatures (`pch infer/score/summarize`, `pch experiment inference/status/compact`), the registry column contract + `run_key`, the invariants (objects-not-stdout, idempotent temp-then-rename `.parts`→`compact`, self-contained folder), and where each artifact lives. Each fact links to its canonical doc.

**Doc ownership** (no duplication — each owns one thing): `RUNNING_INFERENCE.md` (how to run; links the rest), `docs/CLI.md` (command/flag reference), `docs/KEYS.md` (join keys + methods), `docs/SCRIPT_CONTRACTS.md` (M0, script I/O), `docs/HOW_TO_RUN.md` (legacy catalogue, retired post-migration), `CLAUDE.md` `## Docs` index (pointers).

**Docs are a per-milestone deliverable** — each milestone's Definition of Done updates `RUNNING_INFERENCE.md` (+ the relevant reference doc) and the `CLAUDE.md` index for what it shipped. M0 creates `SCRIPT_CONTRACTS.md`; M1 creates `RUNNING_INFERENCE.md` covering `infer` + `experiment inference`/`status`.

---

## Validation strategy

The pipeline is mostly glue around external binaries, so split validation by what's actually testable — no integration tests that need the cluster.

**Unit-tested** (fast, no binaries, deterministic — where bugs hide):
- `resolve_config`: `--method-config` YAML validates and overrides model defaults; `None` → defaults; Pydantic rejects bad configs.
- `build_argv` + artifact-path construction per method.
- `to_registry_row()` keys ⇔ `INFERENCE_REGISTRY_SCHEMA` columns (asserted equal).
- **`compact` merge** — last-writer-wins by `run_key`/`ran_at`, idempotent across reruns. Riskiest logic (concurrency); most tests here.
- registry join keys match the simulation registry.

**Mocked at the subprocess seam:** stub `subprocess.run`; assert the command built and the object assembled from a fake script output.

**Smoke-tested with skip:** one tiny real run per hardened script (M0), `@pytest.mark.skipif(<binary missing>)`. CI without binaries skips; cluster/local runs them.

**Not tested:** phylogenetic correctness of PAUP/ASTRAL output (the tools' job); live SLURM submission (M5 `--dry-run` asserts the sbatch text; real submission manually verified once).

**Static typing (ty) + Pydantic are complementary:** ty checks the typed API end-to-end; the one untyped seam (parsing subprocess stdout) is sealed inside an API function returning a typed object. Pydantic validates external input (the experiment + `--method-config` YAML) at the trust boundary. `make py-static` + `make py-test` green before each commit.

---

## Self-Review

- **Spec coverage** (`specs/cli_specs/human_specs.md`): YAML source of truth, per-method Pydantic config, joinable registry, atomic commands on real+sim data → M1. FN/FP metrics → M2. Methods MP4/GA/ASTRAL3/wASTRAL/TREE-QMC → M1/M3/M4. SLURM + local executor → M5. Script robustness → M0. Artifact model (joinable, no bloat, self-contained, concurrency-safe) → *Pipeline artifact model*. Run manual → *Documentation*. All spec points map to a milestone.
- **Placeholder scan:** M0 + Tasks 1–3 fully specified (code); Tasks 4–7 and M2–M5 at the interface level (signatures given) — flagged, not silent TBDs.
- **Type consistency:** `to_registry_row()` keys (Task 1) ⇔ `INFERENCE_REGISTRY_SCHEMA` (Task 2). `resolve_config → BaseModel` (Task 4) feeds `api.infer(config) → InferenceResult` (Task 5), consumed by `handle_inference` (Task 6), rendered by the CLI (Task 7). `build_argv` (Task 3) called inside `api.infer`. `ScoreResult` (M2) is `score()`'s return — rendered, never parsed back.
