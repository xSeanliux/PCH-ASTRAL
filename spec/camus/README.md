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

- `CamusConfig` in `scripts/lib/experiment.py`. `_GUIDE_TREE_DEPENDENCY` is the
  **allow-list**: a `GuideTree` member absent from it is unsupported, and a field
  validator rejects it at config load.
- `mp` and `ga` remain enum members purely so they fail with an explanation:
  CAMUS demands a rooted binary constraint tree, `mp` is a majority consensus
  (polytomies by construction) and `ga` is unrooted. See `inference.md`.
- Rooting for the PCH methods is to be solved by **adding an outgroup to the
  simulation**, not by post-hoc guessing.
- `TreeInferenceMethod.CAMUS`; runner `scripts/lib/inference/runners/camus.py`.
- `guide_trees` map to **scheduler dependencies** (mp/ga/astral3 → their upstream
  methods; `true_tree` has none, it's the model tree from the sim registry).

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
