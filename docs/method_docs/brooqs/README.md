# BROOQS

BROOQS expands a **tree of blobs** into a **level-1 phylogenetic network**: one cycle and
one hybrid per blob (bioRxiv 2026.08.31.748319 v2). We run it on TOB-QMC's tree of blobs
(`docs/method_docs/tob_qmc/README.md`) as a network method beside CAMUS and SNaQ.
Method key: `brooqs`.

## What it computes

Checked by running the pinned commit, not from the paper; model, objective and search are
under "Unverified".

- **Input:** gene trees, one Newick per line, and a tree of blobs (plain Newick; lengths and
  support unused). Every non-root node with ≥ 3 children, and a root with ≥ 4, is a blob.
- **Output:** one eNewick line: topology only, no γ, no score. Hybrids are 0-indexed
  (`#H0, #H1, …`), one per blob. No blobs: the tree, unchanged.

Deterministic and single-threaded at our flags: identical across runs.

## How we run it

```text
BrooqsRunner                                    scripts/lib/inference/runners/brooqs.py
└── runBROOQS.sh                                scripts/sh/runBROOQS.sh
    ├── model_graph --input         → outgroup  the dataset's model graph
    ├── <cond>/TOB_QMC/trees/N.tree             tree of blobs from `tob_qmc`; must be rooted on the outgroup
    ├── printQuartets               → quartets  PCH-W; each quartet once per unit of weight
    └── python3 bin/brooqs-src/count_quartets.py -i quartets -t tree -o N.net --rooted
                                                BROOQS 17b25b2 (`make install-brooqs`)
```

PCH-W weights are not gene-tree counts, but BROOQS reads repeats as counts, and
multiplicity changes the network (weight-repeated ≠ unique quartets).

The run fails (exit 1, message in the log) when:

| Message | Cause |
|---|---|
| `BROOQS needs an outgroup (simulation.outgroup_label)` | the dataset's model graph has no outgroup |
| `no tree of blobs at … (run tob_qmc first)` | `tob_qmc` has not run in this output dir |
| `tree of blobs … is not rooted on <outgroup>` | `tob_qmc` output from before it rooted on the outgroup (`docs/MIGRATIONS.md`); delete its registry rows and rerun `tob_qmc` |

The rooting check is a prefix test: the tree must start `(<outgroup>,`.

## Configuration

```yaml
simulation:
  outgroup_label: OUT   # required: any label; BROOQS reads it from the model graph
methods:
  tob_qmc: {}   # dependency: the tree of blobs
  brooqs: {}    # no fields
```

Fixed choices, not configurable:

| Choice | Value | Why |
|---|---|---|
| tree of blobs | `tob_qmc`'s (`BrooqsRunner.get_dependencies`) | the only source; a fixed dependency, not a guide tree |
| outgroup | from the model graph | one source of truth, as SNaQ |
| quartets | PCH-W, once per unit of weight | same data as the tree of blobs |
| rooting | `--rooted`, tree of blobs rooted on the outgroup | the paper roots it on the outgroup (§2.3.3); best of three modes, below |
| k | number of blobs | BROOQS has no flag for it |

Rooting mode on one dataset (tree of blobs at alpha 0.25, `t1` as outgroup):

| Mode | FN | FP |
|---|---|---|
| default (may reroot at an arbitrary leaf) | 0.314 | 0.250 |
| `--rooted`, tree as TOB-QMC wrote it | 0.343 | 0.281 |
| `--rooted`, tree rooted on the outgroup | 0.257 | 0.188 |

A binary tree of blobs gives k = 0: an `ok` row, scored. Observed at 30 taxa +
outgroup (FN / FP from `network-score`):

| TOB-QMC alpha | Datasets | Tree of blobs | k | FN / FP |
|---|---|---|---|---|
| 1e-7 (default) | 4 of 4, fixture set | binary | 0 | not scored |
| 1e-7 (default) | 2 of 2, fresh simulation | one degree-4 polytomy each | 1, 1 | 0.387 / 0.367, 0.400 / 0.100 |
| 0.25 | 1 | 5 polytomies (degrees 4, 4, 4, 4, 5) | 5 | 0.194 / 0.286 |
| 0.25 | 1 | 2 polytomies (degrees 6, 5) | 2 | 0.356 / 0.147 |

At the defaults: k = 0 on 4 of 6 datasets, k = 1 on 2.

## Normalising to the network contract

**Point estimate: BROOQS's network, as written** (`N.net`). `--rooted` never reroots, so
it keeps the outgroup's rooting (8 of 8 test runs). If the best hybrid is the group
containing the root, BROOQS takes the next-best. `is_point_estimate_optional` stays False:
BROOQS always writes a network.

**Group estimate: none.** One network, so no family CSV; `network-score` scores the point
estimate, with `edges_added` = its distinct `#H<n>` labels.

Rejected alternatives:
- Renumbering hybrids in the registry: the newick stays "as the tool wrote it".
- A guide-tree config (`GuidedNetworkConfig`): a tree of blobs is not a guide tree.

## Scoring

`network-score` reads the point estimate and runs PhyloNet `CmpNets -m cluster` against the
true network. CmpNets rejects `#H0`, so **scoring renumbers BROOQS's 0-indexed hybrids**
(`renumber_zero_indexed_hybrids` in `score_network`). `guide_tree` in
`network_scores.csv` is null.

## Outputs

`<cond>/BROOQS/networks/`, with `N` = the dataset stem:

| File | Writer | Content |
|---|---|---|
| `N.net` | `count_quartets.py` | point estimate (eNewick) |

The run log is at `<cond>/BROOQS/logs/N.log`; it holds BROOQS's debug matrices.

## Runtime

macOS arm64, 30 taxa + outgroup: 2 s without blobs, 33–78 s with (four datasets, tree of
blobs at alpha 0.25). One 30-taxon run: 43 s, 259 MB on 131,564 weight-repeated quartets.

## Limits

- **4-blobs:** the hybrid of a 4-cycle "is not theoretically identifiable from quartet CFs"
  (paper §2.2.2).
- **FN > 0 whenever h ≥ 1:** reference networks are not level-1, and each contact event is
  two contact edges (`docs/adr/0001-bidirectional-reference-networks.md`); BROOQS gives one
  hybrid per blob.
- **Unusable flags:** `--filter` crashes on quartets (`LinAlgError`); `--dist-var` needs
  branch lengths we lack.
- A quartet leaf absent from the tree of blobs raises `KeyError`, exit 1.

## Versus the BROOQS paper

| | Paper | Here |
|---|---|---|
| tree of blobs | rooted on the outgroup (§2.3.3) | same, by `tob_qmc` |
| flags | none named | `--rooted` |
| gene trees | not checked | PCH-W quartets |

Unverified: a Linux run (built and run on macOS arm64 only); the paper's flags; BROOQS's
model, objective and search.

## References

- BROOQS paper (bioRxiv): [10.64898/2026.08.31.748319](https://www.biorxiv.org/content/10.64898/2026.08.31.748319v2)
- BROOQS, pinned at 17b25b2: [github.com/shayesteh99/BROOQS](https://github.com/shayesteh99/BROOQS)
- TOB-QMC, the tree of blobs: `docs/method_docs/tob_qmc/README.md`
