# SNaQ

SNaQ (Species Networks applying Quartets) infers a **level-1 phylogenetic network** by
maximum pseudolikelihood on quartet concordance factors (Solís-Lemus & Ané 2016). We run it
as a baseline for CAMUS, following the CAMUS paper's wrapper. Method key: `snaq`; kind:
network.

## What it computes

- **Input:** concordance factors (CFs). For each 4-taxon set, the fractions of its quartets
  showing each of the three unrooted topologies, plus `ngenes`, the number of quartets on
  that set.
- **Model:** the network multispecies coalescent. For a level-1 network, the expected CFs of
  every 4-taxon set have a closed form.
- **Objective:** the pseudolikelihood. It sums, over 4-taxon sets, the log-likelihood of the
  observed CFs given the network's expected CFs. SNaQ reports its negative, `-loglik`
  (smaller is better).
- **Search:** hill-climbing from a start tree. Moves add a hybrid (up to `hmax`), move or
  flip a hybrid, or apply an NNI. Branch lengths (coalescent units) and inheritance
  probabilities γ are optimised for each candidate. `runs` independent searches; the best is
  returned.
- **Output:** a *semi-directed* network. Quartet CFs cannot identify the root, so the
  network has no meaningful root.

## How we run it

```text
SnaqRunner.execute                                  scripts/lib/inference/runners/snaq.py
└── runSNAQ.sh --guide-tree G --procs P             scripts/sh/runSNAQ.sh
    ├── model_graph --input        → hmax, OUT      the dataset's model graph (true contact count)
    ├── printQuartets              → quartets       PCH-W; each quartet once per unit of weight
    ├── guide_tree --guide G       → start tree     rooted on OUT, polytomies resolved
    └── run_snaq.jl (12 h cap)                      scripts/jl/run_snaq.jl, SNaQ.jl 1.1.1
        ├── countquartetsintrees   → CFs            4-taxon sets with no quartet dropped
        ├── snaq!(start, CFs; hmax, runs=10, outgroup=OUT, seed=1)
        └── choose                 → N.net, N.choice   point estimate (below)
└── snaq_to_family                 → N.family.csv   group estimate (below)
```

PCH-W weights are not locus counts, so these "CFs" are CF-shaped, but they were not produced
by the coalescent model SNaQ assumes. CAMUS consumes the same weights, so the caveat applies
to the comparison as a whole.

## Configuration

```yaml
methods:
  wastral: {}                  # the guide's method must be enabled: it is a dependency
  snaq:
    guide_trees: [pch_wastral] # start trees; one run per guide
    procs: 10                  # Julia workers; default 1
```

| Field | Meaning |
|---|---|
| `guide_trees` | Start trees, one run each. Any tree method or `true_tree` (`GUIDE_TREES`). `snaq!` resolves polytomies and unroots the start tree itself. |
| `procs` | Julia workers; each runs one of the 10 searches. Not part of `config_hash`: it changes speed, not the result. |

Fixed choices, not configurable:

| Choice | Value | Why |
|---|---|---|
| `hmax` | the dataset's true contact-edge count | as in the paper; an **oracle** setting that needs a simulated dataset |
| `runs` | 10 | SNaQ's default |
| `seed` | 1 | reproducible; SNaQ's `seed=0` means "from the clock" |
| time cap | 12 h (`perl alarm`) | a stuck search fails instead of hanging |
| outgroup | the experiment's `outgroup_label` (required) | rooting, below |

## Normalising to the pipeline contract

Every network method writes a family CSV (`docs/SCHEMAS.md`, `NETWORK_FAMILY_SCHEMA`) and a
point estimate. SNaQ's raw output, `N.networks`, lists the best network, then networks with
the same undirected topology but each hybrid placed elsewhere in its cycle. Rows are sorted
by `-loglik`.

**Point estimate: the best network that can be rooted on the outgroup.** Scoring (CmpNets
`-m cluster`) compares rooted clusters, so the network needs a root, and the true root sits
on the outgroup's edge. `choose` in `run_snaq.jl`:

1. Walks `N.networks` in order: the best first, then alternatives by `-loglik`, skipping
   alternatives whose optimisation failed (`-loglik` -1).
2. Takes the first candidate that `rootatnode!(net, OUT)` accepts. It fails (`RootMismatch`)
   when OUT lies below a hybrid node, because a root there would reverse a hybrid edge.
3. Writes it, rerooted on OUT's edge, as `N.net`, and its 0-based row as `N.choice`.
   (`snaq!` itself roots at OUT's parent node, which leaves a polytomy.)
4. If no candidate fits, it writes `N.choice = none` and no `N.net`. The run is still `ok`
   (`Runner.is_point_estimate_optional`), but nothing is scored.

If the best result is a tree, SNaQ writes no `N.networks`, and `N.net` is the tree.

**Group estimate: `N.family.csv`, one row per `N.networks` line.**

| Column | Value |
|---|---|
| `edges_added` | distinct `#H<n>` labels in the newick |
| `network_newick` | as SNaQ wrote it (lengths, γ); the chosen row holds the rerooted `N.net` |
| `is_best` | true only on the chosen row; none if `N.choice` is `none` |
| `neg_loglik` | SNaQ's `-loglik`; null when it is -1 (failed) or there is no `N.networks` |

### Rejected alternatives

- Scoring SNaQ's arbitrary root: it inflates the error (0.83/0.79 vs 0.44/0.33 FN/FP on one
  smoke dataset that has since been voided).
- Moving hybrids ourselves (`hybridatnode!`).
- Re-orienting every edge away from OUT: this is undefined on odd cycles and discards
  SNaQ's hybrid directions.

## Scoring

`network-score` reads the `is_best` row, strips lengths and γ (`score_network`), and runs
PhyloNet `CmpNets -m cluster` against the true network to get FN and FP rates. Tree
scoring (RF) skips SNaQ. `guide_tree` in `network_scores.csv` is the start tree.

## Outputs

`<cond>/SNAQ/networks/`, with `N` = `<dataset stem>.<guide>`:

| File | Writer | Content |
|---|---|---|
| `N.out`, `N.log`, `N.networks` | `snaq!` | SNaQ's summary, search log, and best + alternatives |
| `N_runs/` | `snaq!` | per-run output |
| `N.net` | `choose` | point estimate (Rich newick), absent if none fits |
| `N.choice` | `choose` | chosen `N.networks` row, or `none` |
| `N.family.csv` | `SnaqRunner.execute` | group estimate |

The run log is at `<cond>/SNAQ/logs/N.log`.

## Runtime

Hours at 30 taxa + OUT: one run did not finish in 65 min. Cost grows with the number of
4-taxon sets (C(31, 4) = 31,465) times the number of candidates. Set `procs: 10` to run the
10 searches in parallel.

## Versus the CAMUS paper

| | Paper | Here |
|---|---|---|
| CFs | `countquartetsintrees` on gene trees (wrapper gist) | same, on PCH-W quartets |
| start tree | a tree given to `snaq!` (gist) | `guide_trees`, default `pch_wastral` |
| `hmax` | given per run (gist) | true contact count |
| runs | `runs = threads` (gist) | 10 |
| seed | 0, i.e. from the clock (gist) | 1 |
| rooting for scoring | not stated | `choose`, above |

Unverified: the paper's run count, its time limit, and which datasets SNaQ finished on. Check
against the paper before quoting them. How the paper rooted SNaQ's networks is an open
question for its authors.

## References

- C. Solís-Lemus, C. Ané (2016). Inferring phylogenetic networks with maximum
  pseudolikelihood under incomplete lineage sorting. *PLoS Genetics* 12(3): e1005896.
  [doi:10.1371/journal.pgen.1005896](https://doi.org/10.1371/journal.pgen.1005896)
- C. Solís-Lemus, P. Bastide, C. Ané (2017). PhyloNetworks: a package for phylogenetic
  networks. *Molecular Biology and Evolution* 34(12): 3292–3298.
  [doi:10.1093/molbev/msx235](https://doi.org/10.1093/molbev/msx235)
- SNaQ.jl, pinned at 1.1.1: [github.com/JuliaPhylo/SNaQ.jl](https://github.com/JuliaPhylo/SNaQ.jl)
- CAMUS paper (bioRxiv): [10.64898/2026.02.01.703143](https://www.biorxiv.org/content/10.64898/2026.02.01.703143v2);
  its SNaQ wrapper: [gist `run_snaq.jl`](https://gist.github.com/jsdoublel/870d2b53e55b105a7954a7b4db291d60)
- C. Than, D. Ruths, L. Nakhleh (2008). PhyloNet: a software package for analyzing and
  reconstructing reticulate evolutionary relationships. *BMC Bioinformatics* 9: 322.
  [doi:10.1186/1471-2105-9-322](https://doi.org/10.1186/1471-2105-9-322)
