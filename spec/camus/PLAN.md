# CAMUS network inference — implementation plan

Terms (contact event, contact edge, h, k, guide tree, base tree, network family): see
`CONTEXT.md`.

## Goal

**Run CAMUS end to end and put raw scores on disk.** Analysis, figures, and comparison
methods come later; this set of PRs lays the groundwork for them.

PCH-ASTRAL infers trees today. CAMUS (Willson & Warnow, Bioinformatics 2026) extends that
to level-1 networks: given a rooted binary guide tree plus quartets, it returns the
optimal network for each k.

**Done when:** `experiments/camus_smoke` — with `outgroup_label: OUT` and both guides — runs
simulation → inference → network-score on a laptop and writes `network_scores.csv`.

PR #31 (open, branch `camus-install`) wired the method in: config, runner, install
scripts, `spec/camus/`. `scripts/sh/runCAMUS.sh` is a stub.

## What CAMUS does

Verified against its Go source and by running `bin/camus`.

1. **It returns a network family, not an estimate.** `-o <prefix>` writes `<prefix>.csv`
   with a row per k (columns `Number of Branches`, `Quartet Satisfied Percent`,
   `Extended Newick`; row 0 is the guide tree, percent hardcoded 0), plus `<prefix>.log`
   and `<prefix>.png`. Rows stop when the score stops improving, so row counts vary and a
   family may be row 0 alone.
2. **It rejects unrooted or non-binary guide trees** (exit 1, no CSV) and ships no rooting
   or refinement code. `mp` is a majority consensus, so polytomies are what it is for, and
   `ga` is unrooted, and TREE-QMC can emit a polytomy (1 of 8 smoke trees); a config
   validator rejects `mp`, `ga` and `pch_w_tree_qmc`. `pch_astral3`, `pch_wastral` and `true_tree`
   are allowed.
3. **It drops every quartet the guide tree already displays**, so inventing a resolution
   for a polytomy would suppress conflicting signal where support is weakest. Rooting must
   come from data, hence the outgroup.
4. **It filters quartets by default** (`-q 2 -t 0.5`). Per 4-taxon set, with topology
   counts c0 ≤ c1 ≤ c2, the minor topologies survive only if `floor(t·(c0+c1)) < c1−c0`.
   Duplicate quartets do count separately, so PCH-W weights reach CAMUS — but through this
   filter, not untouched.
5. **Rooting is structural.** No outgroup marking; rerooting the same tree changes the
   network. Branch lengths are stripped.

How we differ from the paper's evaluation:

| | Paper | Us |
|---|---|---|
| Metric | CmpNets `cluster`, FN and FP | same |
| Reference direction | directed | undirected contact events |
| Reference level | filtered to level-1 | 42% not level-1 |
| k scored | k = 1 only | every k |

## Settled decisions

| Decision | Rationale |
|---|---|
| Record raw, analyse later | We are at "can this run". `network_scores.csv` holds everything CmpNets returns; choosing k, elbow plots, and stratifying by level are analysis. |
| CAMUS flows through `api.infer` and keeps a row in `inference_registry.csv` | `scheduler.get_completed_runs` is the only resume/gate/status ledger. |
| `point_estimate_newick` stays empty for CAMUS | Choosing a k is analysis policy. Empty also makes `handle_score.py:66` skip CAMUS rows — no change to tree scoring. `group_estimate_path` carries the CSV path. |
| Tree and network methods are separate types | `TreeInferenceMethod` and `NetworkInferenceMethod` share the base `InferenceMethod`; one `Runner` base serves both: a tree runner returns a point estimate path, CAMUS returns `None` there and a family path from `get_group_estimate_path`. `api.infer` does not branch on method type. |
| One `api.infer` call per guide tree | CAMUS takes one guide per run. `guide_trees` is a set because `methods:` holds one `camus:` block; `CamusConfig.get_runners()` splits it. Per-guide resume, dependency gating and status line; hashes do not depend on the order written. |
| No `threshold` or filter mode in `CamusConfig` yet | CAMUS defaults apply. Spike data is disposable, so later hash churn is free. Follow-up. |
| A dedicated `camus_registry.py` | Reuse the shard/compact pattern and `current_shard_id`, not the function. |
| The outgroup is kept, never pruned | Matches the paper. Outgrouped error rates, tree scores included, are not comparable to pre-outgroup numbers. |
| The outgroup is known; root on it | Rooting always succeeds mechanically. If ASTRAL attaches `OUT` to the wrong branch, that is pipeline error, measured later — not a gate. |
| Reference = two contact edges per contact event | `docs/adr/0001-bidirectional-reference-networks.md`. |
| `-m cluster` only | `-m tree` returns FN = FP, exceeds 1, and grows with edge count — not an error rate. |
| Networks passed to CmpNets are topology only | Inheritance probabilities crash it (`ExNewickException`). The simulator has no such quantity anyway. |

## PR sequence

| PR | Base | Content |
|---|---|---|
| 0 | `camus-install` | Doc fixes, method/runner type split, guide-tree split; merge #31 |
| GA | `main` | GA NEXUS label fix |
| 1 | `main`, after GA | Outgroup simulation |
| 2 | PR 1 | `runCAMUS.sh`, rooting, pin CAMUS |
| 3 | PR 2 | Network family registry |
| 4 | PR 3 | Network scoring |

---

## PR GA — NEXUS label fix

`scripts/R/inferenceUtils.R:312` labels GA matrix row *i* as `t<i>` by position. It works
today only because columns happen to be `t1…t30` in order. With `OUT` present the
simulator sorts columns lexicographically (`OUT,t1,t10,…`), so OUT's data is labelled
`t1`, t1's `t2`, and a `t31` appears that is not in taxlabels. GA trees feed ASTRAL3's
bipartitions, so the whole `pch_astral3` arm inherits the damage.

**Fix:** `'t', i` → `taxa[i]`, as line 313 already does for TraitLab.

**Test:** write a GA NEXUS from a CSV whose columns are not in numeric order; assert the
matrix row labels equal the taxlabels, in order.

---

## PR 1 — Outgroup simulation

Simulate an extra taxon so inferred trees can be rooted on it. No CAMUS code touched.

```yaml
simulation:
  n_taxa: 30
  outgroup_label: OUT       # omit entirely for no outgroup
```

### Tasks (A–C in parallel, D depends on all)

**A. `scripts/lib/simulation/outgroup.py`**

```python
def graft_tree(newick: str, name: str, root_len: float, og_len: float) -> str:
    """Wrap `newick` so `name` is sister to everything, preserving the terminator."""
    s = newick.strip()
    term = ";" if s.endswith(";") else ""
    return f"({s.rstrip(';')}:{root_len},{name}:{og_len}){term}"


def graft_network(lines: list[str], name: str, root_len: float, og_len: float) -> list[str]:
    """Graft line 1; move each contact `root_len` later, since times count from the root."""
    out = [graft_tree(lines[0], name, root_len, og_len)]
    for line in lines[1:]:
        clade_a, clade_b, time, strength = line.split(";")
        out.append(f"{clade_a};{clade_b};{float(time) + root_len};{strength}")
    return out


def draw_lengths(model_tree: int) -> tuple[float, float]:
    """(root_len, og_len) — deterministic per model tree. Paper's distributions."""
    rng = random.Random(stable_hash_dict({"model_tree": model_tree}))
    return rng.uniform(0.0, 0.1), rng.uniform(0.9, 1.0)
```

**Why the time shift.** `contact_time` is distance from the root (`Network.java:29,312`).
The graft puts a stem above the old root, so every node moves `root_len` later. An
unshifted contact lands before its branch exists; the simulator has no bounds check
(`Network.java:352-353`) and produces a negative branch length silently. 155 of 192
contacts have under 0.05 of margin; the stem is up to 0.1.

The clade fields need no rewriting: the simulator matches them by exact string
(`Network.java:487-496`) and the wrap leaves every inner substring intact.

Branch lengths are the paper's: outgroup `U(0.9, 1.0)`, stem `U(0.0, 0.1)`. Seed on
`model_tree` alone — the base tree is shared across h, so one geometry per base tree keeps
h = 0 vs h > 0 unconfounded.

**B. `scripts/lib/experiment.py`** — `outgroup: str | None = Field(None)` on
`ExperimentSimulationConfig`.

**C. `scripts/py/cli/schemata.py`** — extend `MODEL_GRAPH_REGISTRY` with `outgroup: String`,
`outgroup_seed: Int64`, `outgroup_branch_length: Float64`, `ingroup_stem_length: Float64`.
Null `outgroup_label` records "this run had none". The recorded stem makes the time shift
reversible.

**D. `scripts/py/cli/handle_simulation.py`** — graft at the existing copy step.

- Trees (`:48-51`): write `graft_tree(line, ...)`.
- Networks (`:76-77`): replace `shutil.copy` with read → `graft_network` → write.
- **Fix the bug at `:65-67` in the same change.** `network_registry` records the *source*
  path, not the copy, so simulation reads the originals and grafting would be a silent
  no-op for h > 0. Tree scoring depends on this too: `RFScorer.R` asserts equal tip
  counts, so the registered reference must contain `OUT`.

### Known effects

- Simulator CSV columns become lexicographic (`OUT,t1,t10,…`). Every reader is name-based
  except the GA writer, fixed in PR GA.
- An outgrouped run is not the old run plus one taxon: the extra edges consume RNG draws,
  so the same seed gives different ingroup data.

### Verification

```bash
source scripts/sh/env.sh
uv run python -m pytest tests/scripts/lib/simulation/test_outgroup.py -q
```

Unit: grafting a tree yields 2 root children and 31 tips; `graft_network` leaves clade
fields and strength byte-identical and each time equals original + `root_len`;
`draw_lengths` is stable across calls and differs across model trees; `outgroup: None`
leaves output byte-identical to today.

End to end (needs Java): run `simulation` on `camus_smoke`, then assert every
`model_tree_*.txt` and `model_networks/*.txt` contains `OUT`, `model_graph_registry.csv`
paths point inside the experiment folder with non-null outgroup columns, and simulated
CSVs have 31 taxon columns.

---

## PR 2 — `runCAMUS.sh` and rooting

CAMUS runs and produces its CSV for every guide. The guide-tree split and the
`api.infer` branch for network methods landed in #31.

### Tasks (A, C in parallel; B depends on A)

**A. Rooting helper.** `Tree.root_with_outgroup()` from Biopython, already a dependency.
`scripts/py/root_tree.py` as the shell entry point:

```
python3 -m scripts.py.root_tree -i <tree> -g OUT > rooted.tree
```

Idempotent: `true_tree` arrives rooted, since grafting is the rooting.

**B. `scripts/sh/runCAMUS.sh`** — replace the stub. Match the `runWTREEQMC.sh` /
`runASTRAL3.sh` skeleton. Accepts the flags `CamusRunner.build_argv` already sends:
`--runid --input --name --output --guide-tree`. Steps:

1. Quartets → `"$PCH_SCRATCH/tmp_quartet_$RUNID.txt"` via
   `python3 -m scripts.py.printQuartets -i "$INPUT" > ... || exit 1`.
2. Guide tree → a method guide reads that method's point estimate,
   `<out>/<VARIANT>/trees/<stem>.tree` (`PCH_W_ASTRAL3`, `PCH_W_WASTRAL`);
   `true_tree` reads the grafted base tree via
   `resolve_reference_newick`. Root it (task A).
3. `bin/camus -n "$PROCS" -o "$TREEOUTPUT/CAMUS/networks/$NAME" <guide_tree> <quartets>`,
   then `rc=$?`, the `✅` line, `exit $rc`. No `-t`, no `-q`: CAMUS defaults.

`<name>` is `f"{stem}.{guide}"`, so guides never collide; the upstream tree is named by
`<stem>` alone. Add a `SCRIPT_CONTRACTS.md` row.

**C. Pin CAMUS.** `scripts/sh/installs/install_camus.sh`: `@latest` → `@v1.0.2`. v1.0.1
lacks two fixes (`scoreEdgesDown`, `MakeNetwork` sort) that can affect rows at k ≥ 2.

### Verification

```bash
uv run python -m pytest tests/scripts/lib/inference/ tests/scripts/py/cli/ -q
```

Unit: rooting is idempotent on a rooted tree.

End to end:

```bash
source scripts/sh/env.sh
uv run python -m scripts.py.cli.main experiment inference experiments/camus_smoke/experiment_specification.yaml
head -3 experiments/camus_smoke/inference_data/*/CAMUS/networks/*.pch_astral3.csv
```

Expect a 3-column CSV and `status == ok` in `inference_registry.csv` with an empty
`point_estimate_newick`.

---

## PR 3 — The network family registry

Turn each run's CAMUS CSV into a queryable registry: enrich and concatenate.

**A. Schema** (`schemata.py`): `CAMUS_REGISTRY_SCHEMA` — `dataset_id`, `guide_tree`,
`config_hash`, `runtime_seconds`, `status`, `ran_at`, `log_path`, `k: Int64`,
`qsat_percent: Float64`, `network_newick: String`. `runtime_seconds` is whole-family,
repeated on each row. Only rows CAMUS wrote are stored; nothing is padded to a common k.

**B. `scripts/lib/inference/camus_registry.py`**, mirroring `registry.py`:

- `write_family(result, guide_tree, csv_path, experiment_folder)` — read the CSV, rename,
  prepend identity columns, append one JSON line per row to
  `inference_data/camus_shards/{registry.current_shard_id()}.jsonl`.
- `compact(experiment_folder)` — seed from any existing `camus_registry.csv`, fold in
  shards, key on `dataset_id|config_hash|k`, last-writer-wins by `ran_at`, write
  `inference_data/camus_registry.csv`, unlink shards.

**C. Wiring** in `handle_inference` and `executor.run_compact`. Guard compaction on "camus
shards or camus_registry.csv exists".

### Two traps

1. **Ingest first, then `registry.write_result`.** If the inference row lands and
   ingestion then fails, resume skips that unit forever. On ingestion failure: warn, count
   as `failed`, write no inference row.
2. **Assert the three header names** after `read_csv`. With trap 1, a broken parse becomes
   a retryable failure.

### Verification

Unit: feed a hand-written 3-column CSV through `write_family` + `compact`; assert row
count, renamed columns, and that a second `write_family` for the same key is deduped. Also
a family of row 0 alone.

---

## PR 4 — Network scoring with PhyloNet

Everything `CmpNets -m cluster` returns, per (dataset, guide_tree, k), against the
reference network.

### The reference network

`net{h}-{t}.txt` is the base tree on line 1, then one line per contact event:

```
cladeA;cladeB;contact_time;transmission_strength
```

The clade fields are symmetric. The simulator picks a direction by coin flip per character
and adds one donor state to the recipient's set (`PolymorphicCharacter.java:123-145`).
`transmission_strength` scales the borrowing probability; it is not an inheritance
proportion.

PhyloNet takes Rich newick, where each hybrid node `#Hn` has two parents. The adapter
writes contact event *i* between clades A and B as two contact edges:

```
A_subtree  →  ((A_subtree)#H{2i},#H{2i-1})
B_subtree  →  ((B_subtree)#H{2i-1},#H{2i})
```

The donor point sits above the hybrid point on both branches; the reverse on both makes a
cycle. Verified on 6 taxa: the reference against itself scores 0.0; either
single-direction estimate scores FN 0.167, FP 0; the plain tree scores FN 0.333.

Locate each clade the way the simulator does — exact string match on line 1, anchored on
delimiters so `t2` does not match `t26`. When several contacts land on one branch, nest
them by `contact_time`, earliest outermost. Strip branch lengths last.

### The PhyloNet contract (verified, 3.8.5)

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

- Arguments are bare identifiers from the `NETWORKS` block.
- The newick's own `;` ends the statement. A second one gives `missing END at ';'`.
- Output: `The cluster-based distance between two networks: FN FP AVG`.
- **net1 = reference, net2 = estimate.** Swapping them swaps FN and FP.
- Any level works: level-1 estimates against level-2 and level-3 references run clean,
  values in [0, 1].
- **Mismatched taxon sets return numbers silently.** Guard in Python.
- A contact between sister lineages (a 3-cycle) is invisible: it scores 0.0 against the
  plain tree. Distance 0 does not prove two networks identical.

### Tasks

**A. `scripts/lib/inference/network_format.py`** — the adapter above. Tests: the 6-taxon
case by inspection; two contacts on one branch; a leaf clade whose label prefixes another.

**B. `resolve_reference_network(experiment_folder, horizontal_edges, model_tree)`** in
`scripts/lib/inference/scoring.py`, returning the adapter's output. Sibling of
`resolve_reference_newick`, which stays as is. Mirror its `lru_cache` +
`MODEL_GRAPH_REGISTRY` read.

**C. `network_score(inferred_newick, reference_newick)`** — assert equal taxon sets, write
the NEXUS to a `NamedTemporaryFile`, run the jar with a **2 h timeout**, parse stdout.
Returns FN, FP, AVG and the call's runtime.

**D. `scripts/py/cli/handle_network_score.py` + CLI.** Clone `handle_score.py`'s shape:
same read-back resume, same per-row `try/except → print yellow → continue`, same full
rewrite. It reads `camus_registry.csv`, keys on `(dataset_id, guide_tree, k)`, and its
sim-registry `.select()` must keep `horizontal_edges`.

`network_scores.csv`: `dataset_id`, `guide_tree`, `k`, `fn`, `fp`, `avg`,
`runtime_seconds`, `status` (`ok` | `failed` | `timeout`). Failed and timed-out rows are
written with null scores so a slow network is visible, not missing.

Register as `@experiment.command(name="network-score")` in `main.py`.

### Runtime

Unknown. The paper reports over 5 hours to score one 51-species network and caps scoring
there. We have 31 taxa but unbounded k. The 2 h timeout and the per-row runtime exist to
find out.

### Verification

Unit tests clone `test_handle_score.py`: monkeypatch the scorer, write a real
`model_graph_registry.csv` with an `horizontal_edges >= 1` row, cover writes / dedup /
incremental no-op / timeout row. A live test guarded by
`pytest.mark.skipif(shutil.which("java") is None)`.

```bash
uv run python -m scripts.py.cli.main experiment network-score experiments/camus_smoke/experiment_specification.yaml
```

---

## How a user runs it

```bash
# once
make install-camus install-phylonet
source scripts/sh/env.sh          # required in EVERY shell, including batch jobs

# per experiment
uv run python -m scripts.py.cli.main simulation               experiments/camus_smoke/experiment_specification.yaml
uv run python -m scripts.py.cli.main experiment inference     experiments/camus_smoke/experiment_specification.yaml
uv run python -m scripts.py.cli.main experiment network-score experiments/camus_smoke/experiment_specification.yaml
uv run python -m scripts.py.cli.main experiment status        experiments/camus_smoke/experiment_specification.yaml
```

```yaml
simulation:
  outgroup_label: OUT
methods:
  mp4: {}                       # needed for astral_3's bipartitions
  gray_atkinson: {}             # ditto
  astral_3:
    is_exact: false
    bipartition_strategies: [mp4_trees, ga_trees]
  camus:
    guide_trees: [pch_astral3, true_tree]
```

`camus/pch_astral3` gates on `astral_3`, which gates on `mp4` + `gray_atkinson`.
`camus/true_tree` has no dependency.

## Follow-ups, not in this set

- `experiments/camus_study` on the cluster: 128 datasets, one condition, then more.
- Analysis: k against FN and FP, the distribution of family length, stratifying by
  reference level. Carry the last network forward past the end of a short family, or the
  mean over datasets has survivorship bias.
- Rooting accuracy: does the ingroup root split match the base tree's?
- Quartet filter: `threshold` and filter mode in `CamusConfig`; `-q 0` as an ablation.
- Minimum over single-direction orientations of the reference, from stored newicks.
- Comparison methods: PhyloNet-MPL, SNaQ (`benchmarks.md`).
- How many reference contact events join sister lineages, and are therefore invisible to
  `cluster`.
