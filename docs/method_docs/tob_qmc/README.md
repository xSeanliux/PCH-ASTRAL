# TOB-QMC

TOB-QMC estimates the **tree of blobs** of a species network: the network with each blob
(cycle-bearing region) contracted to one node (Dai, Han & Molloy 2025). It is TREE-QMC's
`--blob` mode. A tree of blobs is not our target network; it is the input that BROOQS
(#57) and NetCS (#58) expand into a level-1 network. Method key: `tob_qmc`.

**Ignore its tree output as a species-tree estimate**, including its RF scores. No network
method accepts it as a guide tree. It is only meaningful as input to BROOQS/NetCS.

## What it computes

- **Input:** gene trees; here, PCH-W (or PCH-W-N) quartets as 4-taxon gene trees.
- **Model:** the network multispecies coalescent. Quartet concordance factors are tested
  with TINNiK's tree test (QTT) and star test (QST) (Allman et al. 2024).
- **Objective:** none optimised. Builds a TREE-QMC base tree, finds each edge's minimum
  p-value over 4-taxon sets around it, and contracts edges with network-like or star signal.
- **Search:** heuristic: per edge, up to 2n² 4-taxon sets (bipartition search).
- **Output:** one tree, rooted on the outgroup, if any; each polytomy is a blob or an edge
  contracted by the star test.

## How we run it

```text
TobQmcRunner.execute                            scripts/lib/inference/runners/tob_qmc.py
├── write_quartets                  → quartets  per quartet_generation; once per unit of weight
└── runTOBQMC.sh --quartets                     scripts/sh/runTOBQMC.sh
    ├── model_graph                 → outgroup
    └── tree-qmc --blob [--root <outgroup>] --alpha A [--3f1a] -w f --override
                                    → N.tree    TREE-QMC 53b15e5, R-embedded build
```

PCH-W weights are not gene-tree counts, but the tests read repeats as counts. Sparse
4-taxon sets fail the tests, so some polytomies come from missing signal, not reticulation.

TREE-QMC roots before testing, and the per-edge search is root-dependent: same base tree,
but edges near a threshold can contract differently (2 more of 28 at `--alpha 0.4`; none
at the defaults).

## Configuration

```yaml
methods:
  tob_qmc:
    alpha: 0.01               # default 1e-7
    three_fix_one_alter: true # default true
    quartet_generation: [PCH_W, PCH_W_N]  # default [PCH_W]; one run each
```

| Field | Default | Flag | Meaning |
|---|---|---|---|
| `alpha` | 1e-7 (TREE-QMC's) | `--alpha` | QTT level: an edge with min p below it becomes a blob. |
| `three_fix_one_alter` | `true` | `--3f1a` | 3-fix-1-alter min p-value search, the paper's. `false`: TREE-QMC's bipartition search. |
| `quartet_generation` | `[PCH_W]` | `--quartets` | Strategies, one run each (`docs/KEYS.md`). Non-`PCH_W` runs write `N.<strategy>.tree`. `PCH_W` is left out of the config JSON, so old hashes hold. |

**Lower alpha for PCH-W input.** A test sees only the quartets of one 4-taxon set:
~20 at 320 characters (a character informs a set only when it splits it 2|2). No p-value
gets near 1e-7, so every tree of blobs is binary and BROOQS/NetCS add nothing. In
`network_experiment` (320 chars, 31 taxa) the smallest QTT p was 0.013 at h = 0 and 0.002
at h = 3; alpha = 0.01 contracts no h = 0 edge.

Fixed choices, not configurable:

| Choice | Value | Why |
|---|---|---|
| `-w f` | unweighted, fast | Same base tree as `-w n`: PCH-W quartets have no polytomies to refine arbitrarily |
| `--beta` (QST level) | 0.95 | TREE-QMC default |
| `--iter_limit_blob` | 2n² | TREE-QMC default; bipartition search only |
| `--root` | the experiment's `outgroup_label`, if any | BROOQS and NetCS need a rooted tree |

One `tob_qmc` config per experiment: every PCH_W config writes the same
`TOB_QMC/trees/N.tree`. BROOQS and NetCS read the tree of their own `quartet_generation`
(`N.tree` or `N.PCH_W_N.tree`).

## Normalising to the tree contract

**Point estimate: TREE-QMC's tree of blobs, as written** (`TOB_QMC/trees/N.tree`). No
group estimate. `tob_qmc` is a `TreeInferenceMethod`: its output is a tree. BROOQS and
NetCS read it as a fixed dependency, not as a guide tree.

## Scoring

`experiment score` RF-scores it against the base tree (h = 0). A contracted blob counts as
false negatives, so this stand-in penalises correct blobs. The right reference is the model
network's tree of blobs; not implemented.

## Outputs

`<cond>/TOB_QMC/`, with `N` = the dataset stem:

| File | Writer | Content |
|---|---|---|
| `trees/N.tree` | `tree-qmc` | point estimate (Newick); `N.PCH_W_N.tree` for PCH_W_N |

The run log is at `<cond>/TOB_QMC/logs/N.log`.

## Runtime

77–120 s per dataset at 30 taxa, 80 characters, about 95k quartets (`tob_qmc_smoke`, #47).

## Versus the TOB-QMC paper

Search: the paper uses 3-fix-1-alter (`--3f1a`), our default. Unverified: its alpha,
beta and runtimes.

## References

- J. Dai, Y. Han, E. K. Molloy (2025). Fast and accurate tree of blobs reconstruction under
  the network multispecies coalescent. *bioRxiv*.
  [doi:10.1101/2025.11.05.686850](https://doi.org/10.1101/2025.11.05.686850)
- E. S. Allman et al. (2024). TINNiK: inference of the tree of blobs of a species network
  under the coalescent model. *Algorithms Mol Biol*.
  [doi:10.1186/s13015-024-00266-2](https://doi.org/10.1186/s13015-024-00266-2)
- TREE-QMC, pinned at 53b15e5: [github.com/molloy-lab/TREE-QMC](https://github.com/molloy-lab/TREE-QMC)
