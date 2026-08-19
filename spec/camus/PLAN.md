# CAMUS network inference — end-to-end implementation plan

## Context

PCH-ASTRAL infers **trees** today. CAMUS (Willson & Warnow, Bioinformatics 2026) extends
that to **level-1 networks**: given a rooted binary constraint tree plus quartets, it
returns the optimal network for each k = number of added reticulation edges. The research
goal is the **elbow** — plot inferred edges (k) against error, per condition, and find
where adding reticulations stops buying accuracy.

PR #31 (merged/open on `camus-install`) wired the method in: config, runner, install
scripts, and `spec/camus/`. `scripts/sh/runCAMUS.sh` is still a stub. This plan takes it
to a working end-to-end pipeline.

Three properties of CAMUS drive every design decision below, all verified against its Go
source rather than its README:

1. **It returns a family, not an estimate.** `-o <prefix>` writes one `<prefix>.csv` with a
   row per k (columns `Number of Branches`, `Quartet Satisfied Percent`, `Extended Newick`;
   row k=0 is the constraint tree), plus `<prefix>.log` and `<prefix>.png`. `m` is
   *discovered* by the DP, never requested, so row counts vary per dataset.
2. **It hard-rejects unrooted or non-binary constraint trees** and ships no rooting or
   refinement code. Measured on our own smoke output: `mp` (majority consensus) has 4 root
   children and 3 polytomies, `ga` has 3 root children. Only `astral3` and `true_tree`
   qualify — already enforced by a config validator.
3. **It deletes every quartet the constraint tree already displays**, so inventing a
   resolution for a polytomy would suppress conflicting signal exactly where support is
   weakest. Rooting must come from data, hence the outgroup.

**Decisions taken with the user:** score by **topological distance to the true network**
(FN/FP, comparable to `scores.csv`), and build the **outgroup first** so both guide trees
work from PR 2 onward.

---

## Cross-cutting design decisions

These are settled; implementers should not re-litigate them.

| Decision | Rationale |
|---|---|
| CAMUS keeps flowing through `api.infer` and keeps a row in `inference_registry.csv` | `scheduler.completed_runs` is the *only* resume/gate/status ledger. Bypassing it means every re-run re-runs the expensive job, submitit's requeue-on-timeout stops being idempotent, and `status` reports `0/N` forever. |
| `point_estimate_newick` stays **empty** for CAMUS | Choosing a k is an analysis policy, not a registry fact. Empty also makes `handle_score.py:66` skip CAMUS rows automatically — **zero changes to tree scoring**. `tree_set_path` carries the CSV path, which is exactly its existing "no single estimate, here is the set" meaning. |
| One `api.infer` call **per guide tree** | `guide_trees` is a list but `config_hash` is per-config. Split into single-guide `CamusConfig(guide_trees=[g])` at scheduling time and pass `name=f"{stem}.{guide}"`. Gives per-guide resume, per-guide dependency gating (`true_tree` runs even if `astral3` is blocked), and hashes that don't churn when the YAML list is reordered. |
| `threshold: float = 0.5` goes into `CamusConfig` **now** | It changes results, so it belongs in `config_hash`. Adding it later invalidates every recorded CAMUS row and orphans registry rows under a dead hash. Process count does **not** go in config — it doesn't change results. |
| A dedicated `camus_registry.py`, not a generalised `registry.py` | Parameterising `compact` means threading output path, shard dir, schema, and key columns through the pipeline's hot path to save ~40 lines of trivial code. Reuse the *pattern* (and `current_shard_id`), not the function. |
| The outgroup is **kept, never pruned** | Matches the paper (species counts are n+1). Keeps the taxon set consistent end to end with no pruning step to get wrong. Consequence: outgrouped error rates are not comparable to pre-outgroup numbers — compare like with like. |

**Task 0 (any PR, 5 min):** copy this plan to `spec/camus/PLAN.md` and link it from
`spec/camus/README.md`, so the spec folder is the single source of truth.

---

## PR 1 — Outgroup simulation

**Goal:** simulate an extra taxon so inferred trees can be rooted on it. Unblocks the
`astral3` guide. No CAMUS code touched — independently reviewable and useful on its own.

**Why first:** `astral3` output is unrooted, so CAMUS rejects it until this lands.

### YAML surface

```yaml
simulation:
  n_taxa: 30
  outgroup: OUT       # omit entirely for no outgroup
```

One optional field — absent means off, present means on with that label. No
`enabled`/`name` pair, so no inconsistent state is representable.

### Tasks (A–C in parallel, D depends on all)

**A. `scripts/lib/simulation/outgroup.py`** — the pure graft.

```python
def graft_outgroup(newick: str, name: str, root_len: float, og_len: float) -> str:
    """Wrap `newick` so `name` is sister to everything, preserving the terminator."""
    s = newick.strip()
    term = ";" if s.endswith(";") else ""
    return f"({s.rstrip(';')}:{root_len},{name}:{og_len}){term}"


def draw_lengths(model_tree: int) -> tuple[float, float]:
    """(root_len, og_len) — deterministic per model tree. Paper's distributions."""
    rng = random.Random(stable_hash_dict({"model_tree": model_tree}))
    return rng.uniform(0.0, 0.1), rng.uniform(0.9, 1.0)
```

Branch lengths are the CAMUS paper's, verbatim from their `add-outgroup.py`: outgroup
`U(0.9, 1.0)`, ingroup stem `U(0.0, 0.1)`. They transfer directly because our base trees
are normalised to max root-to-tip `1.0`, the same scale. `tree_height` scales
`height_factor` in the generated *config*, not the newick, so one policy works everywhere.

**This is a root-level wrap, which is why it also works on network files.**
`net{h}-{t}.txt` is base tree on line 1 then one line per reticulation edge, and each
edge's target is a **verbatim substring of line 1** (verified). Wrapping only prepends `(`
and appends `:len,OUT:len)`, so every internal subtree survives byte-identical and **the
edge lines need no rewriting**. Assert each edge target still appears in the grafted
string, so a future format change fails loudly instead of producing dangling edges.

Seed on `model_tree` alone — deliberately **not** `horizontal_edges`, since the base tree
is shared across h (`net1-1`/`net2-1`/`net3-1` have identical line 1). One geometry per
model tree keeps h=0 vs h>0 comparisons unconfounded.

**B. `scripts/lib/experiment.py`** — add `outgroup: str | None = Field(None)` to
`ExperimentSimulationConfig`.

**C. `scripts/py/cli/schemata.py`** — extend `MODEL_GRAPH_REGISTRY` with `outgroup: String`,
`outgroup_seed: Int64`, `outgroup_branch_length: Float64`, `ingroup_stem_length: Float64`.
Deterministic isn't reproducible until it's written down; the realised lengths are also
exactly what the calibration below plots against. Null `outgroup` records "this run had
none", so pre-outgroup experiments stay distinguishable from the registry alone.

**D. `scripts/py/cli/handle_simulation.py`** — graft at the **existing copy step**, so
`model_graph_registry` and `resolve_reference_newick` pick up grafted versions for free.

- Trees (`:48-51`): write `graft_outgroup(line, ...)` instead of `line`.
- Networks (`:76-77`): replace `shutil.copy` with read → graft line 1 → write.
- **Fix the latent bug at `:65-67` in the same change.** `network_registry` records the
  *source* path, not the copy it just made, so the network copies are currently decorative
  and simulation reads the originals. **Grafting would be a silent no-op for h>0 until
  this is fixed.** Trees already do this correctly; this also stops the two paths
  disagreeing.

### Verification

```bash
source scripts/sh/env.sh
uv run python -m pytest tests/scripts/lib/simulation/test_outgroup.py -q
```

Unit tests (no simulator needed): grafting a tree yields 2 root children and 31 tips;
grafting a network file leaves every edge line byte-identical and every edge target still
a substring; `draw_lengths` is stable across calls and differs across model trees;
`outgroup: None` leaves output byte-identical to today.

End-to-end (needs Java):
```bash
uv run python -m scripts.py.cli.main simulation experiments/camus_study/experiment_specification.yaml
# then assert: every model_tree_*.txt and model_networks/*.txt contains OUT,
# model_graph_registry.csv has non-null outgroup/seed/lengths,
# and simulated CSVs have 31 taxon columns.
```

**Review surface:** ~150 lines. One pure function with tests, one config field, four schema
columns, one integration point, one bug fix.

---

## PR 2 — `runCAMUS.sh`, rooting, and the guide-tree split

**Goal:** CAMUS actually runs and produces its CSV. After this PR both guides work.

### Tasks (A, C, D in parallel; B depends on A)

**A. Rooting helper + CLI.** `Tree.root_with_outgroup()` from Biopython — already a
dependency (`scripts/lib/utils.py` imports `Bio.Phylo`), so no TreeSwift. Add
`scripts/py/root_tree.py` as the shell entry point:

```
python3 -m scripts.py.root_tree -i <tree> -g OUT > rooted.tree
```

Must be idempotent: a tree already rooted on the outgroup passes through unchanged (the
`true_tree` guide arrives rooted, since grafting *is* the rooting).

**B. `scripts/sh/runCAMUS.sh`** — replace the stub. Match the `runWTREEQMC.sh` /
`runASTRAL3.sh` skeleton exactly (that agent's report has the full 7-block shape):
`#!/bin/bash`, vars initialised at top, `while [[ "$#" -gt 0 ]]; do case $1 in` with
one-line arms, combined required-arg check, `PCH_SCRATCH="${PCH_SCRATCH:-$HOME/scratch}"`
+ `mkdir -p`, `mkdir -p` the output dirs, then steps with `✅` echoes.

Accepts the long flags `CamusRunner.build_argv` already sends: `--runid --input --name
--output --guide-trees`. Steps:

1. Quartets → `"$PCH_SCRATCH/tmp_quartet_$RUNID.txt"` via
   `python3 -m scripts.py.printQuartets -i "$INPUT" > ... || exit 1`. PCH-W writes each
   quartet repeated once per unit of weight and CAMUS counts identical quartets, so
   **weights carry over untouched** — the same trick that already works for ASTRAL3.
2. Guide tree → `astral3` reads `<out>/PCH_W_ASTRAL3/trees/<name>.tree`; `true_tree` reads
   the grafted base tree via `resolve_reference_newick`. Then root it (task A).
3. `bin/camus -n "$PROCS" -o "$TREEOUTPUT/CAMUS/networks/$NAME" <const_tree> <quartets>`,
   then `rc=$?`, the `✅` line, `exit $rc`. Do **not** append `|| exit 1` to the final
   binary — that loses the code. `-t` is omitted (0.5 is CAMUS's default and the paper's
   tuned value, per supplementary Figure S2); `-q 2` from their published command is
   obsolete.

Note `<name>` here is `f"{stem}.{guide}"` (task D), so guides never collide. CAMUS's own
`<prefix>.log` lands in `networks/` while `api.infer`'s log is in `logs/` — different
directories, no clash. Add a `SCRIPT_CONTRACTS.md` row (there is currently none for
TREE-QMC either).

**C. `api.infer` newick gate.** `scripts/lib/inference/api.py:50` currently reads the point
estimate unconditionally, which would inline a whole CSV. Gate it:

```python
newick = (
    point_estimate.read_text().strip()
    if ok and getattr(runner, "point_estimate_is_newick", True)
    else ""
)
```

Add `point_estimate_is_newick = False` to `CamusRunner`, and make its
`group_estimate_path` return the same CSV path so `tree_set_path` is populated. Document
the optional attribute in the `Runner` protocol docstring but **do not** add it to the
protocol — five other runners would have to implement it for one method's benefit.

**D. Guide-tree split** in `scripts/py/cli/handle_inference.py`:

```python
def _variants(cfg: BaseModel) -> list[tuple[BaseModel, str | None]]:
    """(config, name-suffix) units to run. CAMUS fans out one run per guide tree so
    each guide gets its own output path, config_hash, and dependency gate."""
    if isinstance(cfg, CamusConfig):
        return [(CamusConfig(guide_trees=[g], threshold=cfg.threshold), g.value)
                for g in dict.fromkeys(cfg.guide_trees)]
    return [(cfg, None)]
```

Wrap the inner `for m in methods:` body in `for cfg, suffix in _variants(base_cfg):`,
compute `ch = config_hash(cfg)` per variant, and pass
`name=f"{input_path.stem}.{suffix}"` when `suffix`. **Dedupe the guide list** —
`prior` is snapshotted before the loop, so a duplicated guide would run twice and write
the same key twice. `select_methods` and `executor._plan` keep using the full config for
ordering (a superset of each variant's deps), so neither changes.

Also add `threshold: float = Field(0.5, ge=0.0, le=1.0)` to `CamusConfig` here.

### Verification

```bash
uv run python -m pytest tests/scripts/lib/inference/ tests/scripts/py/cli/ -q
```

Unit: `_variants` splits two guides into two configs with distinct hashes and dedupes
repeats; `api.infer` returns empty `point_estimate_newick` and a populated `tree_set_path`
for CAMUS (stub `subprocess.run` per `test_api.py`, writing a fake CSV); rooting is
idempotent on an already-rooted tree.

End-to-end smoke — the real proof:
```bash
source scripts/sh/env.sh
uv run python -m scripts.py.cli.main experiment inference experiments/camus_study/experiment_specification.yaml
ls experiments/camus_study/inference_data/*/CAMUS/networks/    # <stem>.<guide>.csv, .log, .png
head -3 experiments/camus_study/inference_data/*/CAMUS/networks/*.astral3.csv
```
Expect a real 3-column CSV with a row per k, and `status == ok` in
`inference_registry.csv` with an empty `point_estimate_newick`.

**Review surface:** ~250 lines, but the shell script is most of it and the Python changes
are small and surgical.

---

## PR 3 — The per-k registry

**Goal:** turn each run's CAMUS CSV into a queryable registry. CAMUS's CSV is *already*
the per-k table, so enrich and concatenate rather than re-derive.

### Tasks

**A. Schema** (`schemata.py`): `CAMUS_REGISTRY_SCHEMA` — `dataset_id`, `guide_tree`,
`config_hash`, `runtime_seconds`, `status`, `ran_at`, `log_path`, `k: Int64`,
`qsat_percent: Float64`, `network_newick: String`. Their three columns rename to
`k` / `qsat_percent` / `network_newick`. No simulation metadata is copied in — the true
`horizontal_edges` is a `dataset_id` join away, exactly as `scores.csv` does it.

**B. `scripts/lib/inference/camus_registry.py`** (~70 lines), mirroring `registry.py`'s
pattern:

- `write_family(result, guide_tree, csv_path, experiment_folder)` — read the CSV, rename,
  prepend identity columns, append one JSON line per row to
  `inference_data/camus_shards/{registry.current_shard_id()}.jsonl`. One writer per shard,
  lock-free, same concurrency story as the existing shards. Reuse
  `registry.current_shard_id()` — the only import needed.
- `compact(experiment_folder)` — seed from any existing `camus_registry.csv`, fold in
  shards, key on `dataset_id|config_hash|k`, last-writer-wins by `ran_at`, write
  `inference_data/camus_registry.csv`, unlink shards. Same crash-tolerant
  `json.JSONDecodeError` skip as `registry._iter_shard_rows`.

**C. Wiring** in `handle_inference` and `executor.run_compact`. Guard compaction on "camus
shards or camus_registry.csv exists" so non-CAMUS experiments don't sprout an empty file.

### Two traps that must be honoured

1. **Ingest first, then `registry.write_result`.** If the inference row lands and ingestion
   then fails, resume permanently skips that unit and the family is lost with no signal.
   On ingestion failure: warn, count as `failed`, write no inference row, let the next run
   retry.
2. **Assert the three expected header names** after `read_csv`. Every newick contains
   commas, so CAMUS must be RFC4180-quoting that column; combined with trap 1, a broken
   parse becomes a retryable failure instead of silent garbage.

### Verification

Unit test feeding a hand-written 3-column CSV through `write_family` + `compact` (no CAMUS
needed) — assert row count, renamed columns, and that a second `write_family` for the same
key is deduped rather than duplicated (this is what makes a requeued SLURM batch safe).

```bash
uv run python -m scripts.py.cli.main experiment inference <spec>
uv run python -c "import polars as pl; d=pl.read_csv('experiments/camus_study/inference_data/camus_registry.csv'); print(d.group_by('guide_tree').len()); print(d.head())"
```

**Review surface:** ~110 lines, one new self-contained module plus a schema and two call
sites.

---

## PR 4 — Network scoring with PhyloNet

**Goal:** FN/FP per (dataset, guide_tree, k) against the **true network**.

This is the hardest PR, and two facts about our reference networks — both measured, not
assumed — reshape it. Read this section fully before starting.

### Fact 1: our reference networks are *contact* networks, not reticulation networks

`net{h}-{t}.txt` is the base tree on line 1, then one line per horizontal edge:

```
t26;t27;0.8409474347897394;0.4222755495151269
((t9:0.0121…,…);(t6:0.0399652665,t4:0.0007173857);0.09405409754271896;0.21922136077561402
```

Each line is **the two clades that connect to each other** (a bare leaf label or a full
subtree newick), then **contact time**, then **transmission strength**. Confirmed against
LingPhyloSimulator `Main/Network.java`: `readFromFile` splits on `;`, asserts 4 fields,
parses `time` and `strength`; `writeNetwork` emits
`newick1;newick2;edge.left.Time;edge.transmission_strength`. The two clade fields are
treated **symmetrically** — there is no donor/recipient direction in the format.

PhyloNet's Rich/extended newick, by contrast, encodes **directed** reticulations: a hybrid
node `#H1` with two parents and an inheritance probability γ. So the adapter is a genuine
semantic conversion, not a reformat, and it must make three explicit choices:

1. **Direction.** An undirected contact event has to become a directed hybrid edge. Pick
   one direction (arbitrary, discards half the event) or emit both (**two** reticulations
   per contact event — which changes both k and the network's level, and would make the
   comparison against a k-edge CAMUS network incoherent). Decide and document; do not let
   this fall out of the implementation by accident.
2. **γ.** `transmission_strength` is plausibly the inheritance proportion but is not
   defined as one. Verify how the simulator actually consumes it before mapping it to γ.
3. **Hybrid node placement.** `contact_time` positions the event on both branches; Rich
   newick encodes position topologically. Converting time → topological position needs the
   branch lengths and a stated convention.

Getting direction backwards would silently produce plausible-but-wrong scores, so the
adapter needs a round-trip test on a hand-built two-taxon case where the answer is known
by inspection.

### Fact 2: the PhyloNet contract, verified — and it handles arbitrary levels

`CmpNets` compares two networks of **any** level (a level-2 network against itself returns
`0.0`), so the comparison is well-posed even though 42% of our references are not level-1
(0/32 at h=1, 14/32 at h=2, 26/32 at h=3). No level flag is stored anywhere: CAMUS emits
level-1 by definition, and a reference's level is a pure function of a file we already
have, computable on demand if an analysis wants to stratify.

The interpretive caveat that remains: CAMUS cannot represent a non-level-1 truth at any k,
so those datasets carry a nonzero error floor. That's the method's hypothesis space, not a
measurement artefact. h=1 is the only fully level-1 condition.

Verified contract (against `bin/PhyloNet.jar` 3.8.5 — full detail in `scoring.md`):

```
#NEXUS
BEGIN NETWORKS;
Network net1 = ((((B)#H1,C),(#H1,D)),A);
Network net2 = (((A,B),C),D);
END;
BEGIN PHYLONET;
CmpNets net1 net2 -m cluster;
END;
```

- Arguments are **bare identifiers** from a `NETWORKS` block — not inline newicks, not
  brace-wrapped sets.
- **The newick's own `;` is the statement terminator** — doubling it gives a misleading
  `missing END at ';'`.
- Methods: `tree`, `tri`, `luay`. Output is
  `The ...-based distance between two networks: FN FP AVG` (`luay` gives one number).
- **net1 = truth, net2 = estimate** — swapping them swaps FN and FP, same convention as
  `RFScorer.R`. Backwards here silently inverts the metric.
- `-m tree` also enforces identical leaf sets; ours always match, so it's a free safety net.

**Use `-m cluster` primary, `-m tree` as a control.** The paper says it uses "the cluster
metric from PhyloNet's CmpNets command". CmpNets actually has nine methods
(`tree|tri|cluster|luay|rnbs|apd|normapd|wapd|normwapd`). On a direction-flipped pair of the
same contact event: `tree` 0.0 (invariant), `cluster` 0.25, `tri` 0.82, `luay` 6.0. Our
contacts have no direction, so `cluster` charges our arbitrary choice as error — but far
less than the alternatives, and it keeps us comparable to published numbers. The `cluster`
vs `tree` gap measures the direction artifact. See `scoring.md`.

### Tasks

**A2. The contact-network → Rich-newick adapter** (`scripts/lib/inference/network_format.py`).
The three choices above, made explicitly and documented in the module docstring, with the
known-by-inspection round-trip test. This is the piece most likely to be silently wrong,
so it should be its own reviewable unit and may deserve splitting into its own PR.

**B. `resolve_reference_network(experiment_folder, horizontal_edges, model_tree)** in
`scripts/lib/inference/scoring.py`, returning the adapter's output. Note the existing
`resolve_reference_newick` correctly hardcodes `horizontal_edges == 0` — that is right for
the **tree** study, where the question is how horizontal transfer degrades *tree* inference
and the underlying tree is the target. Leave it alone; the network path is a sibling, not a
replacement. Mirror its `lru_cache` + `MODEL_GRAPH_REGISTRY` read.

**C. `network_score(inferred_newick, true_network_path)`** — subprocess wrapper following
`summarize.py`/`scoring.py`: build a NEXUS command file in a `NamedTemporaryFile`, run the
jar, parse stdout, raise `RuntimeError` with stderr on non-zero. Returns FN/FP.

**D. `scripts/py/cli/handle_network_score.py` + CLI.** Clone `handle_score.py`'s shape —
same two asserts, same `existing`/`already` read-back resume, same per-row
`try/except → print yellow → continue`, same `pl.concat(...).write_csv(out)` full rewrite.
Differences: it reads `camus_registry.csv` (not the inference registry), keys on
`(dataset_id, guide_tree, k)`, and its sim-registry `.select()` **must keep
`horizontal_edges`** — `handle_score.py:50-53` drops it.

Register as `@experiment.command(name="network-score")` in `main.py` beside
`score_experiment:182`; `name=` is required to get the hyphen.

### Verification

Unit tests clone `test_handle_score.py`: monkeypatch the scorer by module attribute, write
a real `model_graph_registry.csv` with an `horizontal_edges >= 1` row, and cover writes /
dedup / incremental-no-op. A live test guarded by
`pytest.mark.skipif(shutil.which("java") is None)`.

```bash
uv run python -m scripts.py.cli.main experiment network-score <spec>
uv run python -c "import polars as pl; print(pl.read_csv('experiments/camus_study/inference_data/network_scores.csv').head())"
```
Sanity check: FN should be lowest near k == the dataset's true `horizontal_edges`.

**Review surface:** ~200 lines, closely mirroring an existing reviewed file.

---

## PR 5 — The elbow

**Goal:** the actual research output.

Join `network_scores.csv` → `camus_registry.csv` → `simulated_data_registry.csv` (on
`dataset_id`) to recover the true `horizontal_edges`. Plot **x = k, y = FN**, one line per
condition, faceted by guide tree, with a marker at the true edge count. Follow the existing
SciencePlots serif theme already used for paper figures (see recent commits on `main`). Add
it under `scripts/py/analysis/` alongside the current sweep figures.

**Lead with h=1**, the only condition whose references are all level-1 and therefore all
reachable by CAMUS. For h=2/h=3, remember the non-level-1 datasets carry an error floor
(PR 4, Fact 2); if the curves look like they are flattening above zero, check whether that
is the floor before reading it as method error. Level is computable on demand from
`data/base_networks/` if a stratified view is wanted.

**Verification:** run on the smoke experiment; confirm the curve is non-increasing early
and flattens, and that the flattening point tracks the true reticulation count.

---

## How a user runs the whole thing

```bash
# once
make install-camus install-phylonet
source scripts/sh/env.sh          # required in EVERY shell, including batch jobs

# per experiment
uv run python -m scripts.py.cli.main simulation      experiments/camus_study/experiment_specification.yaml
uv run python -m scripts.py.cli.main experiment inference     experiments/camus_study/experiment_specification.yaml
uv run python -m scripts.py.cli.main experiment network-score experiments/camus_study/experiment_specification.yaml
uv run python -m scripts.py.cli.main experiment status        experiments/camus_study/experiment_specification.yaml
```

Full spec (`experiments/camus_study/experiment_specification.yaml`):

```yaml
experiment_folder: experiments/camus_study
simulation:
  n_taxa: 30
  outgroup: OUT                 # PR 1 — required for the astral3 guide
  n_horizontal_edges: [0, 1, 2, 3]
  n_trees: 16
  n_replicas: 2
  base_config_dir: data/base_configs
  base_trees_file: data/trees.txt
  base_networks_dir: data/base_networks
  simulation_params:
    - {poly: high, homoplasy_factor: 0.1, tree_height: 4, n_chars: 320}

methods:
  mp4: {}                       # needed for astral_3's bipartitions
  gray_atkinson: {}             # ditto
  astral_3:
    is_exact: false
    bipartition_strategies: [mp4_trees, ga_trees]
  camus:
    guide_trees: [astral3, true_tree]
    threshold: 0.5
```

Dependencies resolve themselves: `camus/astral3` gates on `astral_3`, which gates on
`mp4` + `gray_atkinson`. `camus/true_tree` has no dependency and runs immediately.
`mp` and `ga` as guides are rejected at config load with an explanation.

---

## The one experiment to run before PR 2

**Calibrate the outgroup.** The paper's branch lengths are tuned for a molecular pipeline
(SiPhyNetwork → PhyloCoalSimulations → INDELible under GTR, ~21% gene-tree error). Ours
feed LingPhyloSimulator's polymorphic character model. The *geometry* transfers because
the tree scale matches; what a branch length means for character evolution does not.

After PR 1, simulate a handful of replicates and check whether ASTRAL actually places `OUT`
as sister to everything else. If it doesn't at our homoplasy levels, outgroup rooting is no
better than midpoint and the approach needs rethinking — far cheaper to learn now than
after PR 4. The calibration harness will want to *set* the two lengths directly rather than
hunt for a seed producing them, so keep the random draw the default path, not the only one.
