# PR #31 review round 2 — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Answer the second review round on PR #31 (`camus-install`): runners own their config and command, every method config exposes `get_runners()`, `dependencies()` is typed on `InferenceMethod`, and the run-space enums live in a `model/` package that neither inference nor config owns.

**Architecture:** `scripts/lib/model/` holds the enums that describe the run space (methods, guide trees, strategies, statuses). Runners are frozen dataclasses built from a config; `RUNNERS` maps method → runner *class* for path lookups. `MethodConfig`'s per-method configs each implement `get_runners() -> list[Runner]`; CAMUS returns one runner per guide. `api.infer` takes a runner. Nothing about on-disk layout, YAML shape, or `config_hash` changes.

**Tech Stack:** Python 3.12, pydantic 2, pytest, `ty`, `ruff`.

**Threads answered:** `runners/base.py:23` (widen to `InferenceMethod`; dependencies are Methods, not Runners, because the scheduler gates on method names), `experiment.py:113` (mandatory `get_runners`, runner owns command + `suffix` + guide), `experiment.py:123` (reply + one comment), `api.py:54` (reply), `api.py:56/57/62` (renames).

## Global Constraints

- Checks: `uv run python -m pytest tests/ -q` (139 pass before this plan), `uv run ty check scripts/lib scripts/py`, `uv run ruff check`, `uv run ruff format`. All clean before each commit.
- No `Any`, no `object` as a type, no `# type: ignore` on lines that can be typed.
- Prose brief; comments say why.
- **Invariant:** `config_hash` of every run is unchanged. A CAMUS run still hashes `CamusConfig(guide_trees={guide})`; tree runs hash their config as before. Registries and resume keys from existing experiments must still match. Pinned by Task 2's `test_camus_runner_config_hash_matches_single_guide_config`.
- **Invariant:** output paths and `name` suffixes unchanged (`<stem>.<guide>` for CAMUS, bare stem otherwise).
- No module in `scripts/lib/inference/runners/` imports `scripts.lib.experiment` at runtime (`TYPE_CHECKING` only). `scripts/lib/model/` imports nothing from `scripts.lib.inference` or `scripts.lib.experiment`. Pinned by Task 1's import test.
- Commit messages: Conventional Commits, trailing `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Branch: `camus-install`, in its own worktree. Upstack merges (Task 4) are the orchestrator's.

## Review Focus

1. Import cycle: `experiment.py` → `runners` → `model` only. Pinned by Task 1's `test_model_has_no_inference_imports` and a clean `python -c "import scripts.lib.inference.runners"`.
2. `config_hash` stability for CAMUS and tree runs. Pinned by Task 2's hash tests.
3. `select_runners` keeps dependency order (mp, ga before astral3; astral3 before camus/astral3). Pinned by the existing `test_select_methods_*` tests, rewritten on runners.
4. `handle_status` and `SlurmExecutor` still label fan-out runs `<method>.<suffix>`. Pinned by existing `test_handle_status` / `test_executor` tests.
5. `pch infer --method camus --method-config f.yaml` with two guides runs twice.

---

### Task 1: `scripts/lib/model/` owns the run-space enums

**Files:**
- Create: `scripts/lib/model/__init__.py`, `scripts/lib/model/methods.py`, `scripts/lib/model/strategies.py`, `scripts/lib/model/guide_tree.py`
- Modify: `scripts/lib/inference/inference.py` (enums out), `scripts/lib/experiment.py` (nested enums become aliases), every file in the import list below
- Test: `tests/scripts/lib/model/test_imports.py`

**Interfaces produced:**
- `scripts.lib.model.methods`: `InferenceMethod`, `TreeInferenceMethod`, `NetworkInferenceMethod`, `RunStatus`, `ConsensusMethod` — bodies moved verbatim from `inference.py`.
- `scripts.lib.model.strategies`: `BipartitionStrategy` (from `ASTRAL3Config`), `NormalisationStrategy` (from `WeightedTreeQMCConfig`) — bodies verbatim.
- `scripts.lib.model.guide_tree`: `GuideTree` and `GUIDE_TREE_DEPENDENCY` — moved from `CamusConfig.GuideTree` / `_GUIDE_TREE_DEPENDENCY`, verbatim, plus the one-line comment the `experiment.py:123` thread asked for.

- [ ] **Step 1: Create the package**

`scripts/lib/model/__init__.py`:

```python
"""The run space: which methods exist, what a guide tree is, which strategies a
method takes. Owned here so neither inference nor config owns the other."""
```

`scripts/lib/model/methods.py`: the five enums from `inference.py` lines 6–31, unchanged.

`scripts/lib/model/strategies.py`:

```python
from enum import IntEnum, StrEnum


class BipartitionStrategy(StrEnum):
    BINARY_CHARACTER = "binary_character"
    MP4_TREES = "mp4_trees"
    GA_TREES = "ga_trees"


class NormalisationStrategy(IntEnum):
    # Values are TREE-QMC --norm_atax args; only 0 and 2 valid for quartet input.
    N0 = 0
    N2 = 2
```

`scripts/lib/model/guide_tree.py`:

```python
from enum import StrEnum

from scripts.lib.model.methods import TreeInferenceMethod


class GuideTree(StrEnum):
    """Which tree constrains the CAMUS network search.

    Membership in `GUIDE_TREE_DEPENDENCY` is the allow-list: a member absent
    from that map is a guide CAMUS cannot accept (see `is_supported`).
    """

    MP = "mp"
    GA = "ga"
    ASTRAL3 = "astral3"
    WASTRAL = "wastral"
    W_TREE_QMC = "w_tree_qmc"
    TRUE_TREE = "true_tree"

    @property
    def is_supported(self) -> bool:
        return self in GUIDE_TREE_DEPENDENCY

    @property
    def dependency(self) -> TreeInferenceMethod | None:
        """The method whose output supplies this guide (None = already have it)."""
        return GUIDE_TREE_DEPENDENCY[self]


# Guide tree -> the method whose output supplies it (None = already have it).
# ONLY these are allowed; absent = CAMUS can't use it. w_tree_qmc is out for now:
# TREE-QMC can emit polytomies, which CAMUS rejects.
# A guide names a method, not a config: MethodConfig holds one config per
# method, so "the astral3 tree" is unique per experiment.
GUIDE_TREE_DEPENDENCY: dict[GuideTree, TreeInferenceMethod | None] = {
    GuideTree.ASTRAL3: TreeInferenceMethod.PCH_ASTRAL3,
    GuideTree.WASTRAL: TreeInferenceMethod.PCH_WASTRAL,
    GuideTree.TRUE_TREE: None,
}
```

- [ ] **Step 2: Point the old homes at the new ones**

`inference.py`: delete the five enum classes; `from scripts.lib.model.methods import InferenceMethod, RunStatus` (the two it still uses). No re-export.

`experiment.py`: delete the nested enums and `_GUIDE_TREE_DEPENDENCY`; keep the nested *names* as aliases so `ASTRAL3Config.BipartitionStrategy`, `WeightedTreeQMCConfig.NormalisationStrategy`, `CamusConfig.GuideTree` still resolve:

```python
class ASTRAL3Config(BaseModel):
    model_config = ConfigDict(frozen=True)
    BipartitionStrategy = BipartitionStrategy  # alias; the enum lives in model/

    bipartition_strategies: list[BipartitionStrategy] = Field(list())
    is_exact: bool
```

Same pattern for the other two. `CamusConfig.guides`, `_reject_unsupported` keep working on `GuideTree`.

- [ ] **Step 3: Migrate every import**

`git grep -l "inference.inference import"` lists 28 files. In each, import the enums from `scripts.lib.model.methods` and keep only `InferenceResult` / `RegistryRow` from `scripts.lib.inference.inference`. `ruff check --fix` removes what became unused. Do not add a compatibility re-export.

- [ ] **Step 4: Import test**

`tests/scripts/lib/model/__init__.py` (empty) and `tests/scripts/lib/model/test_imports.py`:

```python
import sys


def test_model_has_no_inference_imports():
    # model/ describes the run space; it must not know how runs happen.
    for name in list(sys.modules):
        if name.startswith("scripts.lib.inference") or name == "scripts.lib.experiment":
            del sys.modules[name]
    import scripts.lib.model.guide_tree  # noqa: F401
    import scripts.lib.model.strategies  # noqa: F401

    loaded = {n for n in sys.modules if n.startswith("scripts.lib.")}
    assert not {n for n in loaded if n.startswith("scripts.lib.inference")}
    assert "scripts.lib.experiment" not in loaded
```

- [ ] **Step 5: Checks, commit**

```bash
uv run ruff format scripts tests && uv run ruff check --fix scripts tests
uv run ty check scripts/lib scripts/py
uv run python -m pytest tests/ -q      # 140 pass: 139 + the import test
git add scripts/lib/model scripts/lib/inference scripts/lib/experiment.py scripts/py tests
git commit -m "refactor(model): run-space enums move to scripts/lib/model"
```

---

### Task 2: runners own config and command; configs own `get_runners`

**Files:**
- Modify: `scripts/lib/inference/runners/base.py`, `runners/{mp4,ga,astral3,wastral,w_tree_qmc,camus}.py`, `runners/__init__.py`, `scripts/lib/experiment.py`, `scripts/lib/inference/api.py`, `scripts/lib/inference/method_config.py`, `scripts/py/cli/handle_inference.py`, `scripts/py/cli/handle_status.py`, `scripts/lib/inference/executor.py`, `scripts/py/cli/main.py`, `docs/ARCHITECTURE.md`
- Tests: `tests/scripts/lib/inference/test_runners.py`, `test_camus_runner.py`, `test_api.py`, `tests/scripts/py/cli/test_handle_inference.py`, `test_handle_status.py`, `test_main.py`, `tests/scripts/lib/inference/test_executor.py`

**Interfaces produced:**
- `Runner` protocol (instance): `method: InferenceMethod`, `suffix: str | None`, `config: BaseModel`, `build_argv(runid, input_csv, name, output_dir)`, `dependencies() -> list[InferenceMethod]`, `log_path(output_dir, name)`. `TreeRunner` adds `point_estimate_path`, `group_estimate_path`, `consensus_method`; `NetworkRunner` adds `family_path`. Path methods are `@staticmethod` so `TREE_RUNNERS[m].point_estimate_path(...)` works on the class.
- `RUNNERS: dict[InferenceMethod, type[Runner]]`, `TREE_RUNNERS`, `NETWORK_RUNNERS` map method → class.
- `RunnableConfig(BaseModel)` with abstract `get_runners(self) -> list[Runner]`; all six configs subclass it. `CamusConfig.variants()` deleted.
- `api.infer(input_csv, output_dir, runner, *, name=None)`.
- `handle_inference.select_runners(methods: MethodConfig) -> list[Runner]` replaces `select_methods` + `variants`.

- [ ] **Step 1: `runners/base.py`**

```python
from pathlib import Path
from typing import Optional, Protocol

from pydantic import BaseModel

from scripts.lib.model.methods import ConsensusMethod, InferenceMethod


class Runner(Protocol):
    """One run of one method: owns its config, so it owns its command and name."""

    method: InferenceMethod
    suffix: str | None  # distinguishes runs of one method on one dataset
    config: BaseModel  # what config_hash hashes

    def build_argv(
        self, runid: str, input_csv: Path, name: str, output_dir: Path
    ) -> list[str]: ...

    def dependencies(self) -> list[InferenceMethod]:
        """Methods whose output this run consumes; the scheduler orders and gates
        on their names, which is why these are methods and not runners."""
        ...

    @staticmethod
    def log_path(output_dir: Path, name: str) -> Path: ...


class TreeRunner(Runner, Protocol):
    @staticmethod
    def point_estimate_path(output_dir: Path, name: str) -> Path: ...

    @staticmethod
    def group_estimate_path(output_dir: Path, name: str) -> Optional[Path]: ...

    @staticmethod
    def consensus_method() -> Optional[ConsensusMethod]: ...


class NetworkRunner(Runner, Protocol):
    @staticmethod
    def family_path(output_dir: Path, name: str) -> Path: ...
```

- [ ] **Step 2: Runners as frozen dataclasses**

`mp4.py` (template for `ga.py`, `wastral.py`):

```python
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from scripts.lib.model.methods import ConsensusMethod, InferenceMethod, TreeInferenceMethod

if TYPE_CHECKING:
    from scripts.lib.experiment import MP4Config


@dataclass(frozen=True)
class MP4Runner:
    config: "MP4Config"
    method: InferenceMethod = TreeInferenceMethod.MP
    suffix: str | None = None

    def dependencies(self) -> list[InferenceMethod]:
        return []

    def build_argv(self, runid: str, input_csv: Path, name: str, output_dir: Path) -> list[str]:
        return ["bash", "scripts/sh/runMP4.sh", "--runid", runid, "--input", str(input_csv), "--name", name, "--output", str(output_dir)]

    @staticmethod
    def point_estimate_path(output_dir: Path, name: str) -> Path: ...  # unchanged
    # group_estimate_path, consensus_method, log_path unchanged
```

`astral3.py`: `_STRATEGY_SOURCE` / `_STRATEGY_METHOD` key on `scripts.lib.model.strategies.BipartitionStrategy`; `dependencies(self)` and `build_argv(self, ...)` read `self.config`. `w_tree_qmc.py`: `str(self.config.normalisation_strategy.value)`.

`camus.py`:

```python
@dataclass(frozen=True)
class CamusRunner:
    """CAMUS level-1 network inference: one guide tree in, one network family out."""

    guide: GuideTree
    config: "CamusConfig"  # the single-guide config; what config_hash hashes
    method: InferenceMethod = NetworkInferenceMethod.CAMUS

    @property
    def suffix(self) -> str:
        return self.guide.value

    def dependencies(self) -> list[InferenceMethod]:
        return [] if self.guide.dependency is None else [self.guide.dependency]

    def build_argv(self, runid: str, input_csv: Path, name: str, output_dir: Path) -> list[str]:
        return [..., "--guide-tree", self.guide.value]

    # family_path, log_path unchanged
```

`runners/__init__.py`: the three maps hold classes (`MP4Runner`, not `MP4Runner()`), typed `dict[TreeInferenceMethod, type[TreeRunner]]` etc. If `ty` rejects `type[Protocol]`, type them on a `type[MP4Runner] | type[GARunner] | ...` union instead; do not add a cast.

- [ ] **Step 3: Configs own `get_runners`**

In `experiment.py`, before the configs:

```python
class RunnableConfig(BaseModel):
    """A method's YAML block. `get_runners` is the layer between what the YAML
    says and what runs: one runner per unit of work."""

    model_config = ConfigDict(frozen=True)

    def get_runners(self) -> "list[Runner]":
        raise NotImplementedError
```

Each config subclasses it and implements the method; imports of runner classes go at the top of `experiment.py` (`from scripts.lib.inference.runners.mp4 import MP4Runner`, etc. — runners import `experiment` under `TYPE_CHECKING` only, so no cycle). `CamusConfig`:

```python
    def get_runners(self) -> "list[Runner]":
        # CAMUS takes one guide per run; each gets its own config_hash, so the
        # registry key and resume behaviour match a single-guide YAML exactly.
        return [
            CamusRunner(guide=g, config=CamusConfig(guide_trees=frozenset({g})))
            for g in self.guides
        ]
```

Delete `variants()`. `MethodConfigT` in `method_config.py` stays; add `MethodConfig.enabled(self) -> list[RunnableConfig]` returning the non-None fields in declaration order, so `select_runners` needs no `config_for` loop.

- [ ] **Step 4: `api.infer` takes the runner**

```python
def infer(input_csv: Path, output_dir: Path, runner: Runner, *, name: str | None = None) -> InferenceResult:
    name = name or input_csv.stem
    runid = shortuuid.uuid()
    log = runner.log_path(output_dir, name)
    ...
    argv = runner.build_argv(runid, input_csv, name, output_dir)
    ...
    if isinstance(runner, NetworkRunner):  # runtime_checkable protocols, or isinstance on CamusRunner
        # A network family has no single estimate: choosing a k is analysis.
        # ponytail: family-as-CSV is CAMUS's shape; SNaQ/PhyloNet get their own branch.
        family_path = runner.family_path(output_dir, name)
        is_ok = proc.returncode == 0 and family_path.exists()
        tree_set_path = str(family_path) if is_ok else None
    else:
        point_estimate_path = runner.point_estimate_path(output_dir, name)
        is_ok = proc.returncode == 0 and point_estimate_path.exists()
        newick = point_estimate_path.read_text().strip() if is_ok else ""
        group_estimate_path = runner.group_estimate_path(output_dir, name)
        if is_ok and group_estimate_path is not None and group_estimate_path.exists():
            tree_set_path = str(group_estimate_path)
        consensus = runner.consensus_method()
    status = RunStatus.OK if is_ok else RunStatus.FAILED
    return InferenceResult(..., tree_inference_method=runner.method, config_hash=method_config.config_hash(runner.config), method_config_json=runner.config.model_dump_json(), ...)
```

Mark `Runner`, `TreeRunner`, `NetworkRunner` `@runtime_checkable` so the `isinstance` is typed; if `ty` cannot narrow on a runtime-checkable protocol with static methods, branch on `isinstance(runner.method, NetworkInferenceMethod)` and look the class up in `NETWORK_RUNNERS` / `TREE_RUNNERS` as today.

- [ ] **Step 5: Handlers, executor, CLI**

`handle_inference.py`:

```python
def select_runners(methods: MethodConfig) -> list[Runner]:
    """Every unit of work the config asks for, dependencies first."""
    runners = [r for cfg in methods.enabled() for r in cfg.get_runners()]
    order = scheduler.topological_order(
        list(dict.fromkeys(r.method for r in runners)),
        {r.method: r.dependencies() for r in runners},
    )
    return sorted(runners, key=lambda r: order.index(r.method))
```

(`deps_of` keyed by method: two CAMUS runners may differ in dependencies; union them: build `deps_of` as `dict[InferenceMethod, list[InferenceMethod]]` with order-preserving dedup across runners of one method.)

The run loop replaces `for m in methods: for cfg, suffix in variants(...)` with `for r in runners:`; `ch = config_hash(r.config)`; `r.dependencies()`; `name = f"{input_path.stem}.{r.suffix}" if r.suffix else None`; `api.infer(input_path, out_dir, r, name=name)`; `ok_methods.add(r.method.value)`. The `--method` pin filters `runners` by `r.method`. `init_manifest` gets `dict.fromkeys(r.method.value for r in runners)`.

`handle_status.fan_out`: `{m: [(r.suffix, config_hash(r.config)) for r in runners if r.method is m and r.suffix]}`; `labels` unchanged. `executor.py`: `methods = list(dict.fromkeys(r.method for r in select_runners(...)))`; `dep_labels` from the union of `r.dependencies()` over that method's runners. `main.py infer`: `for r in resolve_config(method, method_config).get_runners(): result = api.infer(input, output, r); ...echo...`.

- [ ] **Step 6: Tests**

Rewrite, keeping each existing assertion's meaning:
- `test_runners.py`: build `MP4Runner(MP4Config())` etc.; `build_argv` without `config=`.
- `test_camus_runner.py`: `test_dependencies_drop_true_tree` becomes a `get_runners` test: three guides → three runners with `dependencies()` `[PCH_ASTRAL3]`, `[]`, `[PCH_WASTRAL]`; `test_variants_split_per_guide_in_fixed_order` → `get_runners` suffixes `["astral3", "true_tree"]`; add

```python
def test_camus_runner_config_hash_matches_single_guide_config():
    (r,) = _config(G.ASTRAL3).get_runners()
    assert config_hash(r.config) == config_hash(_config(G.ASTRAL3))
    assert r.config == _config(G.ASTRAL3)
```

- `test_api.py`, `test_main.py`, `test_handle_inference.py`, `test_handle_score.py`, `test_handle_status.py`: fakes become `def fake_infer(input_csv, output_dir, runner, *, name=None)` using `runner.method`, `runner.config`. `test_select_methods_*` → `[r.method for r in select_runners(...)]`.
- `test_executor.py`: only if it monkeypatches `select_methods`.

- [ ] **Step 7: Docs, checks, commit**

`docs/ARCHITECTURE.md`: the line mentioning `CamusConfig.variants()` now says `get_runners()`; one sentence on `model/`.

```bash
uv run ruff format scripts tests && uv run ruff check scripts tests
uv run ty check scripts/lib scripts/py
uv run python -m pytest tests/ -q
git add -A scripts docs tests
git commit -m "refactor(inference): runners own config and command; configs own get_runners"
```

---

### Task 3: Reply on the PR (orchestrator)

One reply per thread, each naming the commit. `experiment.py:123`: the "one config per method" argument from `guide_tree.py`'s comment. `base.py:23`: Methods, not Runners, because the scheduler gates on names. Older threads: point at the smoke run on `camus-registry` (28/28 ok) for the yaml thread; leave the rest for the resolve button.

### Task 4: Propagate upstack (orchestrator)

```
camus-install ──merge──▶ camus-run ──merge──▶ camus-registry ──gh stack sync──▶ camus-scoring/{adapter,scorer,cli}
```

Per merge: resolve, migrate any new `inference.inference` enum imports to `scripts.lib.model.methods` (`scripts/py/guide_tree.py`, `camus_registry.py`, `handle_network_score.py`, their tests), fix `api.infer` fakes, `write_family(result, r.suffix, …)`, run the three checks, push. Then rerun `camus_smoke` inference and `network-score`: both must be no-ops (resume keys unchanged).
