# Weighted TREE-QMC

TREE-QMC infers an **unrooted species tree** from quartets with the Quartet Max Cut (QMC)
framework (Han & Molloy 2023); weighted TREE-QMC accepts weighted quartets (Han & Molloy
2025). We feed it PCH-W quartets with their weights, as an alternative to wASTRAL on the
same input. Method key: `pch_w_tree_qmc`.

## What it computes

- **Input:** weighted quartets, `((A,B),(C,D));w` (TREE-QMC's default quartet format).
- **Model:** no parameters fitted; quartet-based, like ASTRAL (README). The `-w` gene-tree
  weighting schemes do not apply: quartet weights are used as given (`--quartets` path in
  `Instance`, `src/instance.cpp`).
- **Objective:** at each step, a max cut of a quartet graph on the current taxa (MQLib
  heuristic). No global score is reported.
- **Search:** divide and conquer. Each side of the cut is recursed on, with the other side
  replaced by one *artificial taxon*. `--norm_atax` sets how weights of quartets on
  artificial taxa are normalised: `0` none, `2` non-uniform (default). Quartet input
  supports only these two. Deterministic: max-cut seed defaults to 1 (`Instance`, `src/instance.cpp`).
- **Output:** one tree, topology only (no lengths or support). Written with a root of two
  children, but the root is arbitrary. If a subproblem's cut fails, its taxa become a
  polytomy (`construct_stree`, `src/species_tree.cpp`).

## How we run it

```text
WTreeQmcRunner.execute                              scripts/lib/inference/runners/w_tree_qmc.py
└── runWTREEQMC.sh -H R -i CSV -o OUT -V PCH_W_W_TREE_QMC -n N -N 0|2
    │                                               scripts/sh/runWTREEQMC.sh
    ├── scripts.lib.pch --format qfm  → quartets    PCH-W; each quartet once, weight = count
    ├── tree-qmc --quartets --norm_atax K --override → N.tree   bin/tree-qmc, TREE-QMC 4.1.5
    └── leaf-count check                            warns if N.tree has fewer taxa than CSV
```

PCH-W emits no quartet for a taxon sharing no informative state with another, so that
taxon is absent from the tree. The run is still `ok`, but scoring fails (below).

## Configuration

```yaml
methods:
  w_tree_qmc:
    normalisation_strategy: 2   # --norm_atax; 0 or 2, default 2
```

| Field | Meaning |
|---|---|
| `normalisation_strategy` | TREE-QMC `--norm_atax` (`NormalisationStrategy`, `scripts/lib/model/strategies.py`). `0` = none, `2` = non-uniform. Default `2`. `1` is rejected: TREE-QMC lacks it for quartet input. Part of `config_hash` (`hash_config` hashes `{"normalisation_strategy":2}`), so `0` and `2` runs are distinct registry rows. |

Fixed choices, not configurable:

| Choice | Value | Why |
|---|---|---|
| quartet scheme | PCH-W (`WTreeQmcRunner.SCHEME`) | weights carry multiplicity; cf. `pch_wastral` |
| quartet format | qfm, `((A,B),(C,D));w` | TREE-QMC's default |
| `--override` | on | reruns overwrite `N.tree`; without it TREE-QMC writes to stdout |
| max-cut seed | 1 | TREE-QMC default |
| rooting | none (`--root` not passed) | RF scoring unroots anyway |
| version | commit `e577f8c` (4.1.5) | `--quartets` and `--override` exist only in 4.x (`install_w_tree_qmc.sh`) |

## Normalising to the tree contract

**Point estimate: `N.tree`, as TREE-QMC wrote it.** (`WTreeQmcRunner.get_point_estimate_path`)

1. `api.infer` reads it into `point_estimate_newick`; the run is `ok` iff the script exits
   0 and `N.tree` exists.
2. Polytomies are kept. Missing taxa are kept missing (warning only).

**Group estimate: none.** One run gives one tree; `get_group_estimate_path` and
`get_consensus_method` return `None`.

## Scoring

`handle_score` passes the point estimate and the base tree (h = 0,
`resolve_reference_newick`) to `RFScorer.R -m 1` (`score`, `scripts/lib/inference/scoring.py`).
Both are unrooted first; FN and FP rates of nontrivial splits go to `scores.csv`. A polytomy
can raise FN, not FP. A tree missing taxa fails RFScorer's leaf-count assertion; `handle_score`
prints "Scoring failed" and skips the row.

Allowed as a CAMUS guide (`CAMUS_GUIDE_TREES`). It can emit polytomies (1 of 8 smoke
datasets, `spec/camus/inference.md`); the guide builder resolves them arbitrarily, which
biases CAMUS there. SNaQ accepts it.

## Outputs

`<cond>/PCH_W_W_TREE_QMC/trees/`, with `N` = dataset stem:

| File | Writer | Content |
|---|---|---|
| `N.tree` | `tree-qmc` | point estimate (newick, topology only) |

Quartets go to `$PCH_SCRATCH/tmp_quartet_<runid>.txt` and are not cleaned up. The run log is
at `<cond>/PCH_W_W_TREE_QMC/logs/N.log`.

## Runtime

Not measured.

## Versus the weighted TREE-QMC paper

| | Paper | Here |
|---|---|---|
| input | gene trees (paper title) | PCH-W weighted quartets (`--quartets`) |
| quartet weights | from gene-tree support / lengths (`-w`, README) | PCH-W counts |
| `--norm_atax` | `2` default and recommended (README, `src/instance.cpp`) | `2` default; `0` optional |

Unverified: the paper's datasets, settings beyond the README defaults, and whether
non-uniform normalisation is justified for quartet (not gene-tree) input. Check the paper
before quoting them.

## References

- Han, Molloy (2023). Improving quartet graph construction for scalable and
  accurate species tree estimation from gene trees. *Genome Research*.
  [doi:10.1101/gr.277629.122](https://doi.org/10.1101/gr.277629.122)
- Han, Molloy (2025). Improved robustness to gene tree incompleteness, estimation
  errors, and systematic homology errors with weighted TREE-QMC. *Systematic Biology*.
  [doi:10.1093/sysbio/syaf009](https://doi.org/10.1093/sysbio/syaf009)
- TREE-QMC, pinned at `e577f8c` (4.1.5): [github.com/molloy-lab/TREE-QMC](https://github.com/molloy-lab/TREE-QMC)
