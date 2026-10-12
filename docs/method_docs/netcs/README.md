# NetCS

NetCS resolves each blob of degree ≥ 5 in a **tree of blobs** into a cycle with one hybrid
(NetCS preprint, References). It is TREE-QMC's `--network` mode; `tob_qmc` supplies the tree
of blobs. We run it as a network method on PCH-W quartets (#58). Method key: `netcs`.

Facts below were checked by running TREE-QMC `53b15e5` (`spec/netcs/PLAN.md`).

## What it computes

- **Input:** gene trees (here PCH-W quartets as 4-taxon gene trees) and a tree of blobs.
  NetCS does not build the tree of blobs.
- **Model:** unverified (below).
- **Objective:** none reported: the output carries no score.
- **Search:** per blob of degree ≥ 5, one cycle with one hybrid. Smaller blobs stay
  polytomies. No seed flag; the hybrid chosen varies between runs on the same input.
- **Output:** one eNewick line: topology only, no lengths, no γ. Hybrids are 0-indexed
  (`#H0`, `#H1`, …), one per resolved blob. Not binary where a blob is unresolved.

## How we run it

```text
NetcsRunner.execute                              scripts/lib/inference/runners/netcs.py
└── runNETCS.sh                                  scripts/sh/runNETCS.sh
    ├── model_graph --input        → OUT         the dataset's outgroup; none: exit 1
    ├── TOB_QMC/trees/N.tree                     dependency; must start `(OUT,`, else exit 1
    ├── printQuartets              → quartets    PCH-W; each quartet once per unit of weight
    └── tree-qmc --network -i quartets --at N.tree -o N.raw.net --override
                                                 TREE-QMC 53b15e5
└── netcs_to_family                → N.family.csv, N.net   below
```

PCH-W weights are not gene-tree counts; each quartet is repeated per unit of weight. At TOB-QMC's
default alpha our four `OUT` datasets gave binary trees of blobs, so NetCS echoed them:
k = 0, a tree recorded as a network.

## Configuration

```yaml
methods:
  tob_qmc: {}   # dependency: the tree of blobs
  netcs: {}     # no fields
```

The experiment needs `simulation.outgroup_label`.

Fixed choices, not configurable:

| Choice | Value | Why |
|---|---|---|
| tree of blobs | `tob_qmc`'s output (`get_dependencies`) | the only source |
| reticulation count | blobs of degree ≥ 5 | NetCS has no flag |
| `--alpha`, `--beta`, `--iter_limit_blob` | 1e-7, 0.95, 2n² | TREE-QMC defaults |
| `--root` | never passed | segfaults in network mode (`spec/netcs/upstream-root-issue.md`) |
| `--quartets` | never passed | wants a qCF CSV; aborts on quartet lines |
| seed | none | NetCS has no seed flag |

## Normalising to the network contract

**Point estimate: NetCS's network, only if rooted on the outgroup.** Cluster scoring is
root-dependent, and NetCS decides the root:

| `--at` tree rooted on | Log | Output |
|---|---|---|
| a taxon not below a hybrid | "rooting is valid" | Rooted on that taxon. |
| a taxon below a hybrid | "not valid … Perform rerooting on the edge above taxon X" | Rooted elsewhere, a unary node left behind. Exit 0. |
| any, plus `--root <taxon>` | "Rooting species tree at …" | Segfault, exit 139, no file. |

1. `runNETCS.sh` requires the tree of blobs rooted on the outgroup and removes stale
   outputs (`N.net`, `N.raw.net`, `N.family.csv`).
2. `is_rooted_on`: the outgroup is a leaf child of the output's root. A unary `(OUT)` node
   is not.
3. Rooted: `N.net` is a copy of `N.raw.net`.
4. Not rooted: no `N.net`, the family row has `is_best` false, nothing is scored. The run is
   still `ok` (`Runner.is_point_estimate_optional`). No reroot code.

**Not deterministic.** NetCS's hybrid varies per run, and with it whether the input root is
valid. Same input (trees of blobs at TOB-QMC alpha 0.25), 6 runs, three datasets: one
rooted on `OUT` 4 times and not 2; one never (5 distinct roots); one always (byte-identical). Resume keeps the first success,
so whether a dataset has a scored network can depend on that run.

**Group estimate: `N.family.csv`, one row.**

| Column | Value |
|---|---|
| `edges_added` | distinct `#H<n>` labels in the newick; 0 for a tree |
| `network_newick` | `N.raw.net`'s line, as NetCS wrote it |
| `is_best` | the outgroup is a leaf child of the root |

Rejected alternatives:
- Rerooting ourselves: a root below a hybrid is invalid; NetCS did the rooting or nobody does.
- Scoring the arbitrary root (alpha 0.25): FN 0.67 / FP 0.58, against 0.32 / 0.32 rooted
  on `OUT`.
- Repeat-and-vote over runs: analysis, not inference.

## Scoring

`network-score` reads the `is_best` row, strips annotations and renumbers NetCS's 0-indexed
hybrids (`score_network`; CmpNets rejects `#H0`), then runs PhyloNet `CmpNets -m cluster`
against the true network. Tree scoring (RF) skips NetCS. `guide_tree` in
`network_scores.csv` is null. Unresolved blobs (degree < 5) are scored as written.

## Outputs

`<cond>/NETCS/networks/`, with `N` = the dataset stem:

| File | Writer | Content |
|---|---|---|
| `N.raw.net` | `tree-qmc` | the network as NetCS wrote it |
| `N.family.csv` | `NetcsRunner.execute` | group estimate |
| `N.net` | `NetcsRunner.execute` | point estimate: copy of `N.raw.net`; absent if not rooted on the outgroup |

The run log is at `<cond>/NETCS/logs/N.log`; it holds NetCS's rooting verdict.

## Runtime

At 30 taxa, macOS build: 1–3 s per run on a binary tree of blobs, 3–27 s with blobs
(alpha 0.25); 0.8 GB on 131,564 quartets (`spec/netcs/PLAN.md`). The `tob_qmc` dependency dominates (82 s on the same data).

## Versus the NetCS paper

No table: only the abstract was read. Unverified: the model, the paper's alpha and beta, how it
treats blobs of degree < 5, and how it roots.

## References

- NetCS preprint. *bioRxiv*
  [2026.06.06.730607](https://www.biorxiv.org/content/10.64898/2026.06.06.730607v2)
- TREE-QMC, pinned at 53b15e5: [github.com/molloy-lab/TREE-QMC](https://github.com/molloy-lab/TREE-QMC)
- Tree of blobs: `docs/method_docs/tob_qmc/README.md`
