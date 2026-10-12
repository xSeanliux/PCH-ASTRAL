# PhyloNet-MPL(FT)

PhyloNet's `InferNetwork_MPL` infers a **rooted phylogenetic network** with k reticulations by
maximum pseudo-likelihood on rooted triples of gene trees (Yu & Nakhleh 2015). "FT" (fixed
tree) means the search keeps a given start tree as backbone and only adds reticulations. The
CAMUS paper's main baseline; same interface as CAMUS (guide tree + quartets). Method key:
`phylonet_mpl`.

## What it computes

- **Input:** rooted gene trees, here 4-taxon ones; a start tree; k.
- **Model:** the network multispecies coalescent; rooted-triple probabilities have a closed form.
- **Objective:** the log pseudo-likelihood over rooted triples, `Total log probability`
  (higher is better).
- **Search:** heuristic hill-climbing that adds k reticulations to the fixed start tree
  (`-fs`); 10 runs (`-x` default); a run stops after 100 failed proposals in a row; no
  examination cap.
- **Output:** rooted networks with branch lengths and γ, best first. Not restricted to level-1.

## How we run it

```text
PhyloNetMPLRunner.execute                           scripts/lib/inference/runners/phylonet_mpl.py
└── runPhyloNetMPL.sh --guide-tree G --procs P      scripts/sh/runPhyloNetMPL.sh
    ├── phylonet_mpl_nexus         → N.nex          scripts/py/phylonet_mpl_nexus.py
    │   ├── ModelGraph.from_dataset → k, OUT        the dataset's model graph (true contact count)
    │   ├── build_guide_newick      → start tree    rooted on OUT
    │   └── root_quartets           → gene trees    PCH-W quartets holding OUT, rooted on it,
    │                                               once per unit of weight
    └── InferNetwork_MPL (all) k -s st -fs -pl P    PhyloNet 3.8.5 → N.result
└── phylonet_mpl_to_family         → N.family.csv, N.net
```

Quartets without OUT cannot be rooted, so they are dropped. PCH-W weights are not gene-tree
counts; CAMUS consumes the same weights, so the caveat applies to the comparison as a whole.

## Configuration

```yaml
methods:
  wastral: {}                  # the guide's method must be enabled: it is a dependency
  phylonet_mpl:
    guide_trees: [pch_wastral] # fixed trees; one run per guide
    procs: 10                  # PhyloNet -pl threads; default 1
```

| Field | Meaning |
|---|---|
| `guide_trees` | Fixed trees, one run each. `PHYLONET_MPL_GUIDE_TREES`: `pch_astral3`, `pch_wastral`, `true_tree`, `ga`. Others are rejected at config load: `-fs` keeps the tree, so it must be binary as estimated (`tob_qmc` is a tree of blobs, not a species tree). |
| `procs` | PhyloNet `-pl` threads. Not part of `config_hash`: it changes speed, not the result. |

Fixed choices, not configurable:

| Choice | Value | Why |
|---|---|---|
| k | the dataset's true contact-edge count | an **oracle** setting that needs a simulated dataset |
| runs, failures, examinations | PhyloNet defaults (10, 100, unlimited) | as the paper's wrapper |
| outgroup | `simulation.outgroup_label` (required) | roots gene trees and start tree |
| time cap | none | the scheduler's job limit; a 12 h cap is a follow-up |

## Normalising to the network contract

**Point estimate: PhyloNet's first network, as written** (`N.net`). It is rooted: gene trees
and start tree are rooted on OUT.

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
(RF) skips it. `guide_tree` in `network_scores.csv` is the fixed tree.

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

## Runtime

Hours. A 26-taxon run (hand-pruned model, voided) was stopped after 10.5 h; it explored
2,107 backbone trees, so `-fs` did not fix the tree. PhyloNet uses the fixed-tree search
only if the start network parses; why it did not here is open. At 5 taxa: k = 1 in 15 s,
k = 2 in 32 s (`spec/camus/benchmarks.md`).

## Versus the CAMUS paper

| | Paper | Here |
|---|---|---|
| command | `InferNetwork_MPL -s start -fs` (`spec/camus/benchmarks.md`) | same, `(all)` gene trees |
| gene trees | gene trees | PCH-W quartets holding OUT, rooted on it |
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
