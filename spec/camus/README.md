# CAMUS network studies

Extends the pipeline from tree inference to **level-1 phylogenetic network**
inference (CAMUS) and network **scoring** (PhyloNet). Config-driven and
CLI-controlled, matching the existing YAML conventions.

## Tools

### CAMUS — network inference
- Repo: https://github.com/jsdoublel/camus (Go)
- Dynamic-programming algorithm: infers a level-1 network from **quartets + a
  rooted binary constraint (guide) tree**, maximizing quartet agreement while
  containing the guide tree.
- Input: a constraint tree (rooted binary newick) + gene trees (newick, labels ⊆
  constraint tree). Output: level-1 networks in **extended newick**, one per k
  (number of added reticulation edges).
- CLI: `camus [-f fmt -o prefix -t thresh -n procs -q mode] <const_tree> <gene_trees>`
- Install: `scripts/sh/installs/install_camus.sh` → `GOBIN=bin go install
  github.com/jsdoublel/camus@latest` → `bin/camus`. Needs Go on PATH.

### PhyloNet — network scoring / benchmark
- Repo: https://github.com/NakhlehLab/PhyloNet (Java)
- Run: `java -jar bin/PhyloNet.jar cmd.nex` (NEXUS command file).
- Used to **score** an inferred network against the reference network
  (`CmpNets -m cluster`, FN/FP) — the metric the paper uses.
- Install: `scripts/sh/installs/install_phylonet.sh` → downloads
  `PhyloNet.jar` (v3.8.5) into `bin/PhyloNet.jar`.

## Model extension (`methods: camus:`)

```yaml
methods:
  camus:
    guide_trees:
      - astral3     # guide = PCH-ASTRAL3           (dep: pch_astral3)
      - wastral     # guide = PCH-wASTRAL           (dep: pch_wastral)
      - true_tree   # guide = simulation base tree  (no dep)
```

CAMUS takes one guide tree per run; `guide_trees` is a set that fans out to one run
per guide (`CamusConfig.get_runners()`), each named `<stem>.<guide>`. `experiment
status` counts each guide on its own line, `camus.<guide>`.

`CamusConfig` in `scripts/lib/experiment.py`; runner
`scripts/lib/inference/runners/camus.py`. `GUIDE_TREE_DEPENDENCY`
(`scripts/lib/model/guide_tree.py`) is both the
**allow-list** (absent member = unsupported, rejected by a field validator at config
load) and the scheduler-dependency map — a method guide gates on its method,
`true_tree` on nothing. `mp`/`ga`/`w_tree_qmc` stay enum members only so they fail
with an explanation; why, and the rooting plan, are in `inference.md` and `outgroup.md`.

CAMUS is a `NetworkInferenceMethod`, not a `TreeInferenceMethod`. Its runner is a
`NetworkRunner`: it names a family path, not a point estimate.

## The pipeline, end to end

1. **Simulate with an outgroup.** Graft `OUT` as sister to the old root of the base
   tree/network, then simulate as usual — every dataset now has n+1 taxa. Branch
   lengths and seeding: `outgroup.md`.
2. **Get a guide tree.** Inferred (`astral3`, `wastral`) or `true_tree`
   (the grafted base tree). See the rooted-binary constraint in `inference.md`.
3. **Root it on the outgroup.** ASTRAL's output is unrooted, so reroot on `OUT`
   (Biopython `root_with_outgroup`). `true_tree` is already rooted — grafting *is* the
   rooting — so this is a no-op for it. Either way CAMUS gets a rooted binary tree.
4. **Run CAMUS** on that guide tree plus PCH-W quartets as its gene trees. Weights
   arrive as repeated lines, then pass CAMUS's default quartet filter. Out comes a
   network family, one network per k.
5. **Record** the family: CAMUS's own per-k CSV, enriched with our identity columns
   and concatenated → `camus_registry.csv` (`registry.md`).
6. **Score with PhyloNet**, outgroup retained, per (dataset, guide_tree, k) →
   `network_scores.csv` (`scoring.md`). Analysis comes later.

## This PR's scope (wiring only)

- Install scripts for both binaries + Makefile `install-camus` / `install-phylonet`.
- `camus:` model extension wired end-to-end into the inference pipeline.
- `scripts/sh/runCAMUS.sh` is a **stub** (no-op, exits 0) — smoke run in
  `experiments/camus_smoke/` proves it's invoked per dataset and guide. Runs report
  FAILED because the stub writes no family; that's expected until inference lands.

**`PLAN.md` is the plan of record** — the PR sequence from outgroup simulation to raw
network scores, with per-PR verification and the settled decisions. Start there. Where
another file here disagrees with it, `PLAN.md` wins. Terms: `CONTEXT.md`.

Supporting detail: `inference.md` (real runCAMUS.sh + the rooted-binary constraint),
`outgroup.md` (simulate an outgroup so PCH trees can be rooted), `registry.md`
(network family registry — CAMUS emits a family, not one estimate),
`scoring.md` (PhyloNet scoring: the measurements behind the metric choice),
`benchmarks.md` (quartet-based network methods to compare against — SNaQ, and
PhyloNet-MPL fed quartets as incomplete gene trees).
