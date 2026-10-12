# PhyloNet-MPL(FT)

PhyloNet's `InferNetwork_MPL` infers a **rooted phylogenetic network** with k reticulations by
maximum pseudo-likelihood on rooted triples of gene trees (Yu & Nakhleh 2015). "FT" (fixed
tree, `-fs`) is meant to keep a start tree as backbone and only add reticulations; in our
build it does not (see [Fixed tree](#fixed-tree)). The CAMUS paper's main baseline; same interface as CAMUS (guide tree + quartets). Method key:
`phylonet_mpl`.

## What it computes

- **Input:** rooted gene trees, here 4-taxon ones; a start tree; k. PhyloNet reads each gene
  tree's triples from its Newick root, never rerooting (`computeTripleFrequenciesFromSingleGT`),
  so an unrooted tree gets whatever root its parentheses imply.
- **Model:** the network multispecies coalescent; rooted-triple probabilities have a closed form.
- **Objective:** the log pseudo-likelihood over rooted triples, `Total log probability`
  (higher is better).
- **Search:** heuristic hill-climbing from the start tree (`-fs`: `treeAugmentInferNetworkMPL`); 10 runs (`-x` default); a run stops after 100 failed proposals in a row; no
  examination cap.
- **Output:** rooted networks with branch lengths and γ, best first. Not restricted to level-1.

## How we run it

```text
PhyloNetMPLRunner.execute                           scripts/lib/inference/runners/phylonet_mpl.py
└── runPhyloNetMPL.sh --guide-tree G --procs P      scripts/sh/runPhyloNetMPL.sh
    ├── phylonet_mpl_nexus         → N.nex          scripts/py/phylonet_mpl_nexus.py
    │   ├── ModelGraph.from_dataset → k, OUT        the dataset's model graph (true contact count)
    │   ├── build_guide_newick      → start tree    rooted on OUT, no branch lengths
    │   └── root_quartets           → gene trees    every PCH-W quartet, rooted by the guide,
    │                                               one `[&W weight]` line per rooted quartet
    └── InferNetwork_MPL (all) k -s st -fs -pl P    PhyloNet 3.8.5 → N.result
└── phylonet_mpl_to_family         → N.family.csv, N.net
```

Weights go in as Rich Newick tree probabilities (`Tree gt0 = [&W 7] ...`): PhyloNet adds a
tree's weight to its topology's count, so this equals repeating the line 7 times (same tree,
same score range on a 6-taxon test) in at most 3·C(n, 4) lines (94,395 at 31 leaves) instead
of one per unit of weight (~1e6). PCH-W weights are not gene-tree counts; CAMUS consumes the
same weights, so the caveat applies to the comparison as a whole.

### Rooting quartets

PCH-W quartets are unrooted; MPL needs rooted ones. Each two rootings of one quartet give
different triples: `((a,b),(c,d))` → ab|c, ab|d, cd|a, cd|b; `(a,(b,(c,d)))` → cd|b, cd|a,
bc|a, bd|a. `root_quartets` roots each quartet where the guide (rooted on OUT) places the root
of its four taxa:

| Guide's first split of {a,b,c,d} | Quartet ab\|cd rooted |
|---|---|
| 1\|3, x first (e.g. x = d) | on x's pendant edge: `(((a,b),c),d)` |
| 2\|2 | on its central edge: `((a,b),(c,d))`, even if the guide splits ac\|bd |

A quartet with OUT is rooted on OUT. Rooting by OUT alone would keep only those, about 4/n of
the weight (~13% at 31 leaves); rooting by the guide keeps all of it, at the cost of biasing
the triples toward the guide's root placement.

### Branch lengths

- **Gene trees:** topology only. Quartets have no lengths, and PhyloNet keys gene trees by
  topology (it sets their lengths to -∞ before counting).
- **Start tree:** none (`root_topology` strips them); MPL optimises lengths and γ itself.
  Giving lengths does not change the search (tested below).
- **Output:** lengths in coalescent units and γ, fitted to triple frequencies from PCH-W
  weights, which are not coalescent counts: not interpretable as times. Stripped at scoring.

## Configuration

```yaml
methods:
  wastral: {}                  # the guide's method must be enabled: it is a dependency
  phylonet_mpl:
    guide_trees: [pch_wastral] # start tree + quartet rooting; one run per guide
    procs: 10                  # PhyloNet -pl threads; default 1
```

| Field | Meaning |
|---|---|
| `guide_trees` | Start trees and quartet rootings, one run each. `PHYLONET_MPL_GUIDE_TREES`: `pch_astral3`, `pch_wastral`, `true_tree`, `ga`. Others are rejected at config load: the guide roots every quartet, so it must be binary as estimated (`tob_qmc` is a tree of blobs, not a species tree). |
| `procs` | PhyloNet `-pl` threads. Not part of `config_hash`: it changes speed, not the result. |

Fixed choices, not configurable:

| Choice | Value | Why |
|---|---|---|
| k | the dataset's true contact-edge count | an **oracle** setting that needs a simulated dataset |
| runs, failures, examinations | PhyloNet defaults (10, 100, unlimited) | as the paper's wrapper |
| outgroup | `simulation.outgroup_label` (required) | roots the guide, which roots the quartets |
| time cap | none | the scheduler's job limit; a 12 h cap is a follow-up |

## Normalising to the network contract

**Point estimate: PhyloNet's first network, as written** (`N.net`). It is rooted: gene trees
and start tree are rooted by the guide, itself rooted on OUT.

**Group estimate: `N.family.csv`, one row per network in `N.result`, best first.**

| Column | Value |
|---|---|
| `edges_added` | distinct `#H<n>` labels in the newick |
| `network_newick` | as PhyloNet wrote it (lengths, γ) |
| `is_best` | true on the first row only |
| `log_probability` | PhyloNet's `Total log probability` |

A result with no network fails the run (`phylonet_mpl_to_family` raises).

## Scoring

`network-score` reads the `is_best` row, strips lengths and γ (`score_network`), and runs
PhyloNet `CmpNets -m cluster` against the true network to get FN and FP rates. Tree scoring
(RF) skips it. `guide_tree` in `network_scores.csv` is the guide.

## Outputs

`<cond>/PHYLONET_MPL/networks/`, with `N` = `<dataset stem>.<guide>`:

| File | Writer | Content |
|---|---|---|
| `N.result` | PhyloNet | networks, best first, with log probabilities |
| `N.net` | `PhyloNetMPLRunner.execute` | point estimate (Rich newick) |
| `N.family.csv` | `PhyloNetMPLRunner.execute` | group estimate |

The NEXUS is at `$PCH_SCRATCH/tmp_phylonet_mpl_<runid>.nex`. PhyloNet's per-proposal
`logfile.txt` (~150 MB/h) goes to `/dev/null`. The run log is at
`<cond>/PHYLONET_MPL/logs/N.log`.

## Fixed tree

`-fs` does not keep the start tree in PhyloNet 3.8.5. With default settings it does select
`treeAugmentInferNetworkMPL` (`_oneGTPerLocus && _fixStartSpeciesNetwork && start != null`),
yet a test with 6 taxa, k = 1, `-x 2`, 70 gene trees `((((a,b),c),(d,e)),O)` plus 30
`((((a,b),(c,d)),e),O)`, and a deliberately wrong start tree `((((a,e),d),(b,c)),O)`
returned networks with cherry (a,b), absent from the start tree, with or without start-tree
branch lengths. Why is open; until then, read "FT" as "start tree", not "fixed".

## Runtime

Hours. A 26-taxon run (hand-pruned model, voided) was stopped after 10.5 h; it explored
2,107 backbone trees, consistent with the tree not being fixed. At 5 taxa: k = 1 in 15 s,
k = 2 in 32 s (`spec/camus/benchmarks.md`).

## Versus the CAMUS paper

| | Paper | Here |
|---|---|---|
| command | `InferNetwork_MPL -s start -fs` (`spec/camus/benchmarks.md`) | same, `(all)` gene trees |
| gene trees | gene trees, as given (wrapper gist) | PCH-W quartets, rooted by the guide |
| start tree | wASTRAL | `guide_trees`, default `pch_wastral` |

Unverified: the paper's k, run count and time limit; that MPL(FT) completed up to 51 species
(`spec/camus/benchmarks.md` cites the paper; not rechecked).

## References

- Y. Yu, L. Nakhleh (2015). A maximum pseudo-likelihood approach for phylogenetic networks.
  *BMC Genomics* 16(Suppl 10): S10.
  [doi:10.1186/1471-2164-16-S10-S10](https://doi.org/10.1186/1471-2164-16-S10-S10)
- D. Wen, Y. Yu, J. Zhu, L. Nakhleh (2018). Inferring phylogenetic networks using PhyloNet.
  *Systematic Biology* 67(4): 735–740.
  [doi:10.1093/sysbio/syy015](https://doi.org/10.1093/sysbio/syy015)
- PhyloNet, pinned at 3.8.5: [github.com/NakhlehLab/PhyloNet](https://github.com/NakhlehLab/PhyloNet)
- CAMUS paper (bioRxiv): [10.64898/2026.02.01.703143](https://www.biorxiv.org/content/10.64898/2026.02.01.703143v2)
