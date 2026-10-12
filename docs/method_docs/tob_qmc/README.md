# TOB-QMC

TOB-QMC estimates the **tree of blobs** of a species network: the network with each blob
(cycle-bearing region) contracted to one node (Dai, Han & Molloy 2025). It is TREE-QMC's
`--blob` mode. A tree of blobs is not our target network; it is the input that BROOQS
(#57) and NetCS (#58) expand into a level-1 network. Until those land, we run it alone and
score it as a tree. Method key: `tob_qmc`.

**Ignore its tree output as a species-tree estimate**: its RF scores, and any run that
uses it as a guide tree (SNaQ accepts it, as it accepts every tree method). It is only
meaningful as input to BROOQS/NetCS.

## What it computes

- **Input:** gene trees; here, PCH-W quartets as 4-taxon gene trees.
- **Model:** the network multispecies coalescent. Quartet concordance factors are tested
  with TINNiK's tree test (QTT) and star test (QST) (Allman et al. 2024).
- **Objective:** none optimised. Builds a TREE-QMC base tree, finds each edge's minimum
  p-value over 4-taxon sets around it, and contracts edges with network-like or star signal.
- **Search:** heuristic: per edge, up to 2n² 4-taxon sets (bipartition search).
- **Output:** one unrooted tree; each polytomy is a blob or an edge contracted by the star
  test.

## How we run it

```text
TobQmcRunner (default execute)                  scripts/lib/inference/runners/tob_qmc.py
└── runTOBQMC.sh                                scripts/sh/runTOBQMC.sh
    ├── printQuartets               → quartets  PCH-W; each quartet once per unit of weight
    └── tree-qmc --blob --override  → N.tree    TREE-QMC 53b15e5, R-embedded build
```

PCH-W weights are not gene-tree counts, but the tests read repeats as counts. Sparse
4-taxon sets fail the tests, so some polytomies come from missing signal, not reticulation.

## Configuration

```yaml
methods:
  tob_qmc: {}   # no fields
```

Fixed choices, not configurable:

| Choice | Value | Why |
|---|---|---|
| `--alpha` (QTT level) | 1e-7 | TREE-QMC default |
| `--beta` (QST level) | 0.95 | TREE-QMC default |
| `--iter_limit_blob` | 2n² | TREE-QMC default |

## Normalising to the tree contract

**Point estimate: TREE-QMC's tree of blobs, as written** (`TOB_QMC/trees/N.tree`). No
group estimate. `tob_qmc` is a `TreeInferenceMethod`: its output is a tree, and network
methods will consume it the way they consume guide trees.

## Scoring

`experiment score` RF-scores it against the base tree (h = 0). A contracted blob counts as
false negatives, so this stand-in penalises correct blobs. The right reference is the model
network's tree of blobs; not implemented.

## Outputs

`<cond>/TOB_QMC/`, with `N` = the dataset stem:

| File | Writer | Content |
|---|---|---|
| `trees/N.tree` | `tree-qmc` | point estimate (Newick) |

The run log is at `<cond>/TOB_QMC/logs/N.log`.

## Runtime

77–120 s per dataset at 30 taxa, 80 characters, about 95k quartets (`tob_qmc_smoke`, #47).

## Versus the TOB-QMC paper

Unverified: the paper's alpha, beta and search settings, and its runtimes.

## References

- J. Dai, Y. Han, E. K. Molloy (2025). Fast and accurate tree of blobs reconstruction under
  the network multispecies coalescent. *bioRxiv*.
  [doi:10.1101/2025.11.05.686850](https://doi.org/10.1101/2025.11.05.686850)
- E. S. Allman et al. (2024). TINNiK: inference of the tree of blobs of a species network
  under the coalescent model. *Algorithms Mol Biol*.
  [doi:10.1186/s13015-024-00266-2](https://doi.org/10.1186/s13015-024-00266-2)
- TREE-QMC, pinned at 53b15e5: [github.com/molloy-lab/TREE-QMC](https://github.com/molloy-lab/TREE-QMC)
