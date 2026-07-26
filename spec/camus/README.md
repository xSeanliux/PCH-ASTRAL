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
- Used to **score** an inferred network against gene trees (e.g. `CalGTProb`,
  pseudo-likelihood added in 3.8.5) — the benchmark scoring the paper uses.
- Install: `scripts/sh/installs/install_phylonet.sh` → downloads
  `PhyloNet.jar` (v3.8.5) into `bin/PhyloNet.jar`.

## Model extension (`methods: camus:`)

```yaml
methods:
  camus:
    guide_trees:
      - astral3     # guide = PCH-ASTRAL3           (dep: pch_astral3)
      - true_tree   # guide = simulation base tree  (no dep)
```

`CamusConfig` in `scripts/lib/experiment.py`; runner
`scripts/lib/inference/runners/camus.py`. `_GUIDE_TREE_DEPENDENCY` is both the
**allow-list** (absent member = unsupported, rejected by a field validator at config
load) and the scheduler-dependency map — `astral3` gates on PCH_ASTRAL3, `true_tree`
on nothing. `mp`/`ga` stay enum members only so they fail with an explanation; why,
and the rooting plan, are in `inference.md` and `outgroup.md`.

## The pipeline, end to end

1. **Simulate with an outgroup.** Graft `OUT` as sister to the old root of the base
   tree/network, then simulate as usual — every dataset now has n+1 taxa. Branch
   lengths and seeding: `outgroup.md`.
2. **Get a guide tree.** Either `astral3` (inferred) or `true_tree` (the grafted model
   tree). Only these two — see the rooted-binary constraint in `inference.md`.
3. **Root it on the outgroup.** ASTRAL's output is unrooted, so reroot on `OUT`
   (Biopython `root_with_outgroup`). `true_tree` is already rooted — grafting *is* the
   rooting — so this is a no-op for it. Either way CAMUS gets a rooted binary tree.
4. **Run CAMUS** on that constraint tree plus PCH-W quartets as its gene trees
   (weights carry over as repeated lines). Out comes a family of networks, one per k.
5. **Record** the family: CAMUS's own per-k CSV, enriched with our identity columns
   and concatenated → `camus_registry.csv` (`registry.md`).
6. **Score with PhyloNet**, outgroup retained, per (dataset, guide_tree, k) →
   `network_scores.csv`, giving the inferred-edges vs error elbow (`scoring.md`).

## This PR's scope (wiring only)

- Install scripts for both binaries + Makefile `install-camus` / `install-phylonet`.
- `camus:` model extension wired end-to-end into the inference pipeline.
- `scripts/sh/runCAMUS.sh` is a **stub** (no-op, exits 0) — smoke run in
  `experiments/camus_smoke/` proves it's invoked per dataset. Runs report FAILED
  because the stub emits no network (`api.infer` requires the point-estimate
  file); that's expected until inference lands.

Future work: `inference.md` (real runCAMUS.sh + the rooted-binary constraint),
`outgroup.md` (simulate an outgroup so PCH trees can be rooted), `registry.md`
(per-k network registry — CAMUS emits a network family, not one estimate),
`scoring.md` (PhyloNet scoring, elbow of inferred-edges vs FN error).
