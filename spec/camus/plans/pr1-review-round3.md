# PR #31 review round 3 — implementation plan

Delta on `camus-install@2d60205` (round 2, `spec/camus/plans/pr1-review.md`: configs own
`get_runners()`, runners own config + command, enums in `scripts/lib/model/`). Round 2 is
committed locally, not pushed.

**Goal:** one `Runner` contract for tree and network methods; guide trees are tree
methods; registry and score tables share names and carry `method`; naming rules applied;
docs describe the layers, seams, files and schemas.

## Global constraints

- Checks, all clean before every commit: `uv run python -m pytest tests/ -q`,
  `uv run ty check scripts/lib scripts/py`, `uv run ruff check`, `uv run ruff format`.
  Environment: sandbox refuses `source`; set `PYTHONPATH=. PCH_SCRATCH=$TMPDIR` inline if a
  test needs it. Record the pass count before you start and after.
- No `Any`, no `object` as a type, no avoidable `# type: ignore`, no `cast` to dodge a
  real type error.
- Brevity: code, comments, docs, commit messages. Comments say why.
- **Naming rules** (apply to every symbol this PR stack adds or changes, not the whole repo):
  - booleans `is_X` (also locals: `heavy` → `is_heavy`);
  - mappings `X_to_Y`, plural/singular respected (`METHOD_TO_RUNNER_CLASS`);
  - functions and methods are verb phrases (`get_log_path`, `hash_config`). Properties
    and dataclass fields stay nouns.
- **Docstrings:** every function/method touched gets a brief reST docstring:
  one summary line, then `:param x:` / `:returns:` / `:raises X:` only where not obvious.
- Commits: Conventional Commits, ending with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Never push, never comment on GitHub. The orchestrator does both after user approval.
- `config_hash` changes for CAMUS runs (guide values change). Deliberate; see MIGRATIONS.
  Tree-method hashes must NOT change — pin with a test.

## Branches

Work happens in worktree `.claude/worktrees/camus-registry` (other worktrees hold
`camus-install`, `camus-run`; do not touch them, do not `git -C` into them).

```
r3/camus-install  (from camus-install@2d60205)   Task A, B
r3/camus-run      (from camus-run, merge r3/camus-install)        Task C1
camus-registry    (merge r3/camus-run)                            Task C2
camus-scoring/{adapter,scorer,cli} (merge down the stack)         Task C3
```

Upstack uses merges, not rebases: these branches are pushed PRs.

## Schedule (parallel)

```
wave 1 (parallel, separate worktrees):
  A   code            r3/camus-install
  B   docs            r3/docs        (from camus-install@2d60205; merged into r3/camus-install after A)
  C2+C3 layer-local   camus-registry, then camus-scoring/{adapter,scorer,cli}
                      schema + renames in each layer's OWN files only; keep old
                      #31 names (tree_set_path, RUNNERS, ...) — the merge fixes them
wave 2 (serial): merge A+B → r3/camus-run (C1) → camus-registry → scoring stack;
                 fix call sites; append SCHEMAS/MIGRATIONS entries per layer
wave 3 (parallel): review + smoke (Task D)
```

---

## Task A — code, on `r3/camus-install`

### A1. One `Runner` base class (`scripts/lib/inference/runners/base.py`)

Replace the `Runner`/`TreeRunner`/`NetworkRunner` protocols with one generic abstract
base. Nominal inheritance removes round 2's protocol-invariance workaround.

```python
@dataclass(frozen=True)
class Runner(ABC, Generic[ConfigT]):        # ConfigT bound to BaseModel; covariant if ty needs it
    config: ConfigT                           # what hash_config hashes

    @property
    @abstractmethod
    def method(self) -> InferenceMethod: ...  # subclasses narrow to Tree/NetworkInferenceMethod

    @property
    def suffix(self) -> str | None: return None      # distinguishes runs of one method on one dataset

    def get_run_name(self, stem: str) -> str: ...    # stem, or f"{stem}.{suffix}"

    @abstractmethod
    def build_argv(self, runid: str, input_csv: Path, name: str, output_dir: Path) -> list[str]: ...

    def get_dependencies(self) -> list[InferenceMethod]: return []

    @staticmethod @abstractmethod
    def get_log_path(output_dir: Path, name: str) -> Path: ...

    @staticmethod @abstractmethod
    def get_point_estimate_path(output_dir: Path, name: str) -> Path | None: ...

    @staticmethod
    def get_group_estimate_path(output_dir: Path, name: str) -> Path | None: return None

    @staticmethod
    def get_consensus_method() -> ConsensusMethod | None: return None
```

- Path getters stay static: `guide_tree.py` looks a point estimate up by method alone.
- Every runner subclasses `Runner[<ItsConfig>]`; drop the per-runner `isinstance`
  asserts and methods that now equal the default.
- `CamusRunner`: `get_point_estimate_path` returns `None` with
  `# ponytail: no rule for picking a k yet; add one when analysis picks it`;
  `get_group_estimate_path` returns `CAMUS/networks/<name>.csv`. Delete `family_path`.
- `runners/__init__.py`: one map `METHOD_TO_RUNNER_CLASS: dict[InferenceMethod, type[Runner[...]]]`
  (insertion order = scheduler tie-break, keep the comment). Delete `RUNNERS`,
  `TREE_RUNNERS`, `NETWORK_RUNNERS`, `TreeRunner`, `NetworkRunner` everywhere.

### A2. `api.infer` loses its branch

```python
def infer(input_csv: Path, output_dir: Path, runner: Runner[...]) -> InferenceResult:
    name = runner.get_run_name(input_csv.stem)
    ...
    point_estimate_path = runner.get_point_estimate_path(output_dir, name)
    group_estimate_path = runner.get_group_estimate_path(output_dir, name)
    required_path = point_estimate_path or group_estimate_path
    assert required_path is not None, f"{runner.method} declares no estimate"
    is_ok = proc.returncode == 0 and required_path.exists()
    newick = point_estimate_path.read_text().strip() if is_ok and point_estimate_path else ""
    # group path recorded only when the file exists (None = "no set")
```

The `name=` kwarg goes; callers stop building `f"{stem}.{suffix}"`.

### A3. Guide trees are tree methods (`scripts/lib/model/guide_tree.py`)

Delete the `GuideTree` enum and `GUIDE_TREE_DEPENDENCY`. Replace with:

```python
TRUE_TREE: Final = "true_tree"
GuideTree = TreeInferenceMethod | Literal["true_tree"]
# Rooted binary only. mp is a majority consensus (polytomies), ga is unrooted,
# TREE-QMC can emit polytomies; CAMUS rejects all three.
# A guide names a method, not a config: MethodConfig holds one config per method.
SUPPORTED_GUIDE_TREES: Final[frozenset[GuideTree]] = frozenset(
    {TreeInferenceMethod.PCH_ASTRAL3, TreeInferenceMethod.PCH_WASTRAL, TRUE_TREE}
)
```

- `CamusConfig.guide_trees: frozenset[GuideTree]`; validator rejects anything outside
  `SUPPORTED_GUIDE_TREES` with a message listing the supported values.
- `CamusRunner.guide` (property): the single guide. `get_dependencies()` → `[]` for
  `true_tree`, else `[guide]`. `suffix` → `str(guide)` (`pch_astral3`, `true_tree`).
  `--guide-tree` passes the same string.
- YAML becomes `guide_trees: [pch_astral3, true_tree]`: update
  `experiments/camus_smoke/experiment_specification.yaml` and every doc/spec example.
- Tests: YAML strings parse to the right members; `mp`, `ga`, `pch_w_tree_qmc` rejected;
  runners sorted, suffixes `["pch_astral3", "true_tree"]`; CAMUS runner hash equals
  hash of the single-guide config.

### A4. Registry row names

- `InferenceResult.tree_inference_method` → `method`; `tree_set_path` → `group_estimate_path`
  (also `RegistryRow`).
- `INFERENCE_REGISTRY_SCHEMA`: column `tree_set_path` → `group_estimate_path`. No
  read-time compatibility shim; old files are migrated by hand (Task B, MIGRATIONS.md).

### A5. Naming sweep (the symbols this PR touches)

| Old | New |
|---|---|
| `Runner.dependencies` / `log_path` / `point_estimate_path` / `group_estimate_path` / `consensus_method` | `get_dependencies` / `get_log_path` / `get_point_estimate_path` / `get_group_estimate_path` / `get_consensus_method` |
| `RUNNERS` | `METHOD_TO_RUNNER_CLASS` |
| `METHOD_CONFIG` | `METHOD_TO_CONFIG_CLASS` |
| `config_hash()` | `hash_config()` (the registry column stays `config_hash`) |
| `MethodConfig.enabled()` | `get_enabled_configs()` |
| `scheduler.topological_order` | `sort_topologically` |
| `scheduler.completed_runs` | `get_completed_runs` |
| `dependencies_by_method` / local `deps_of` | `map_method_to_dependencies` / `method_to_dependencies` |
| `handle_status.fan_out` / `labels` / `FanOut` | `get_fan_out` / `build_labels` / `MethodToRuns` |
| `ASTRAL3Runner._STRATEGY_SOURCE` / `_STRATEGY_METHOD` / `_bipartition_sources` | `_STRATEGY_TO_SOURCE` / `_STRATEGY_TO_METHOD` / `_get_bipartition_sources` |
| executor local `heavy` | `is_heavy` |

Grep for any other boolean, mapping or function the PR diff (`git diff main...HEAD`)
introduces and apply the rules. List every rename in the commit body.

### A6. Tests

Rewrite tests to the new names; keep each assertion's meaning. Add:
- `api.infer` with a runner whose point path is `None`: OK iff group file exists;
  `point_estimate_newick == ""`, `group_estimate_path` set.
- tree-method `hash_config` unchanged: hard-code today's hash of `MP4Config()` and
  `ASTRAL3Config(is_exact=False)` (compute once before editing) and assert equality.

Commit A as 1–3 commits (e.g. runner contract; guide trees; renames).

---

## Task B — docs, on `r3/camus-install` (after A)

Visual style: show the smallest view that makes the point — call tree, shallow file
tree, Mermaid, or a table. Brief prose next to each.

1. **`docs/ARCHITECTURE.md`** — keep what is still true, rewrite the rest:
   - **Layers**, as one diagram: `model/` (run-space enums) → config
     (`experiment.py` YAML models, `method_config.py`) → runners (`get_runners()` turns a
     config into units of work; a runner owns argv, paths, dependencies) → orchestration
     (`handle_inference`, `scheduler`, `executor`, `api.infer` = the only subprocess site)
     → registries (`registry.py` shard/compact) → scoring.
   - **Seams**: where to extend for a new tree method, a new network method, a method
     that fans out, a new guide tree, a new registry table. One line each: file + what to
     write.
   - **Files written**: shallow tree of `<experiment>/simulation_data` and
     `inference_data` with which code writes each.
   - **Invariants**: OK rule (point estimate, else group estimate), resume key
     `(dataset_id, method, config_hash)`, success-only ledger, dependency gate on method
     name.
2. **`docs/SCHEMAS.md`** (new): one section per table — path, writer, key, columns
   (name, type, meaning), join keys. Source of truth is `scripts/py/cli/schemata.py`; say
   so at the top. Tables on this branch: `model_graph_registry`, `config_registry`,
   `simulated_data_registry`, `inference_registry`, `scores`.
3. **`docs/MIGRATIONS.md`** (new): for agents fixing old experiment folders.
   - `inference_registry.csv`: rename `tree_set_path` → `group_estimate_path`
     (polars one-liner).
   - CAMUS guide values changed (`astral3` → `pch_astral3`, `wastral` → `pch_wastral`):
     CAMUS `config_hash`es changed. Drop CAMUS rows from `inference_registry.csv`, delete
     `inference_data/*/CAMUS/`, rerun inference.
   - (Upstack layers append their own entries.)
4. `docs/CLI.md`, `docs/RUNNING_INFERENCE.md`: replace inline column lists with a link to
   `SCHEMAS.md`; fix stale names.
5. `CLAUDE.md` Docs list: add `SCHEMAS.md`, `MIGRATIONS.md`.
6. `spec/camus/*.md`: fix `GuideTree`, `family_path`, `tree_set_path`, `astral3` guide
   values, `TreeRunner`/`NetworkRunner`. Do not rewrite history sections; fix current
   claims only.
7. Commit this plan as `spec/camus/plans/pr1-review-round3.md`.

---

## Task C — upstack (serial, one layer at a time)

Each layer: merge the layer below, resolve, apply that layer's items, run all checks,
commit. Same naming and docstring rules for symbols the layer introduces.

**C1. `r3/camus-run`** (branch from `camus-run`, merge `r3/camus-install`)
- `scripts/py/guide_tree.py`: `--guide` parses `true_tree` or a `TreeInferenceMethod`
  value; reject unsupported. Look up `METHOD_TO_RUNNER_CLASS[m].get_point_estimate_path`;
  assert not `None`. Rename functions to verb phrases (`experiment_of` →
  `find_experiment`, `model_tree_of` → `find_model_tree`, `base_tree_of` →
  `find_base_tree`, `guide_newick` → `build_guide_newick`, `rooted_topology` →
  `root_topology`, or better verbs).
- `runCAMUS.sh`, outgroup code: apply rules only to what this layer touched.

**C2. `camus-registry`** (merge `r3/camus-run`)
- `CAMUS_REGISTRY_SCHEMA`: add `method` (after `dataset_id`); drop `runtime_seconds`,
  `status`, `log_path` (join `inference_registry` on `(dataset_id, method, config_hash)`).
  Keep `ran_at` (per-family dedup). Key `dataset_id|method|config_hash|k`; family dedup
  per `(dataset_id, method, config_hash)`.
- `write_family` reads `result.group_estimate_path`; `guide_tree` from `runner.suffix`.
- Wiring in `handle_inference` still branches on `isinstance(method, NetworkInferenceMethod)`;
  add `# ponytail: CAMUS-shaped family CSV; generalise to network_registry with a 2nd network method`.
- Rename per rules (`shards_dir` → `get_shards_dir`, `registry_path` →
  `get_registry_path`, …).
- `SCHEMAS.md`: add `camus_registry`. `MIGRATIONS.md`: "delete `camus_registry.csv` and
  `camus_shards/`, rerun inference (rows re-ingest)".

**C3. `camus-scoring/{adapter,scorer,cli}`** (merge down: adapter ← camus-registry,
scorer ← adapter, cli ← scorer)
- `NETWORK_SCORES_SCHEMA`: add `method`; `fn` → `fn_rate`, `fp` → `fp_rate`; drop `avg`.
  Key `(dataset_id, method, config_hash, k)`; keep `guide_tree` label.
- `network_score` → verb (`score_network`); return no `avg`.
- Rename per rules in each layer's own code.
- `SCHEMAS.md`: add `network_scores`. `MIGRATIONS.md`: "delete `network_scores.csv`, rerun".
- Top layer: update `spec/camus/PROGRESS.md` and `HANDOFF.md` (round 3 done; push + PR
  replies pending user approval).

---

## Task D — verify (orchestrator)

1. Fresh-eyes review of `git diff camus-install..r3/camus-install` against this plan.
2. Smoke on top of the stack: move `experiments/camus_smoke/inference_data` aside, rerun
   `experiment inference` and `experiment network-score`. Expect 28/28 ok, 72 family
   rows, 72 `ok` scores; rerun is a no-op.
3. Ask the user before: pushing (`r3/camus-install:camus-install`,
   `r3/camus-run:camus-run`, the rest), updating the #31 body, replying to threads.
