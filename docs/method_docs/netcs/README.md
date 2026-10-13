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
NetcsRunner                                      scripts/lib/inference/runners/netcs.py
└── runNETCS.sh                                  scripts/sh/runNETCS.sh
    ├── model_graph --input        → OUT         the dataset's outgroup; none: exit 1
    ├── TOB_QMC/trees/N.tree                     dependency; missing: exit 1
    ├── printQuartets              → quartets    PCH-W; each quartet once per unit of weight
    └── tree-qmc --network -i quartets --at N.tree -o N.net --override
                                                 TREE-QMC 53b15e5
```

PCH-W weights are not gene-tree counts; each quartet is repeated per unit of weight.

At TOB-QMC's default alpha NetCS has returned only k = 0, a tree recorded as a network:
4 of 4 fixture datasets gave binary trees of blobs, echoed; 2 of 2 freshly simulated ones
gave one degree-4 polytomy, kept unresolved.

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

**Point estimate: `N.net`, rerooted on the outgroup if it can be, else as NetCS wrote it.**
NetCS decides the root first:

| `--at` tree rooted on | Log | Output |
|---|---|---|
| a taxon not below a hybrid | "rooting is valid" | Rooted on that taxon. |
| a taxon below a hybrid | "not valid … Perform rerooting on the edge above taxon X" | Rooted elsewhere, a unary node left behind. Exit 0. |
| any, plus `--root <taxon>` | "Rooting species tree at …" | Segfault, exit 139, no file. |

`NetcsRunner.execute` then tries `reroot_on(network, outgroup)`:
- No hybrid above the outgroup: `N.net` is the network rerooted on it (topology only;
  only edges on the root-to-outgroup path flip), and it is scored.
- A hybrid above the outgroup: no valid root there. `N.net` stays as NetCS wrote it; its
  score is null (below).

On our data the reroot never rescues a network: all 11 distinct outputs NetCS rerooted have
the outgroup below a hybrid, and the 9 it kept were rooted on `OUT` already.

### Why rerooting with a tree library is valid

`Bio.Phylo` knows no networks; `reroot_on` works because of how eNewick writes one.

**A hybrid node is written twice**, since Newick gives a node one parent:

```text
(a,(b)#H0)   inner #H0: carries the hybrid's clade.   P1 → H, and H → b
(d,#H0)      leaf #H0: a pointer, no children.        P2 → H
```

Nesting is parent → child, so both occurrences say "my parent points into H": those are
the two hybrid edges. No edge joins the two occurrences; they are one node. Which one
carries the clade is the writer's choice.

**Which roots are valid.** NetCS's network is semi-directed: hybrid edges are directed,
tree edges are not. A root is valid iff it is not downstream of a hybrid node. The file
has some root, which we assume valid; then the clade under an inner `#H<n>` is exactly
what is downstream of that hybrid, wherever the root is. So:

```text
the outgroup is downstream of a hybrid
  ⇔ it is written inside the clade of an inner #H<n>
  ⇔ one of its ancestors in the parsed tree is named #H<n>     (reroot_on's check)
```

**Why the flip is safe.** To Bio the file is a tree with two unrelated nodes named
`#H0`. Rerooting on a leaf reverses only the edges on the old-root-to-leaf path. `P2 → H`
is on that path only if the outgroup is the pointer leaf (never); `P1 → H` only if the
outgroup is under the inner `#H0` (rejected above). No hybrid edge flips, the labels are
written back unchanged, and the result is the same network with a new root.

**Forcing it anyway** flips a hybrid edge and makes a directed cycle (the pointer ends up
inside its own clade); CmpNets then dies with `StackOverflowError`. Seen on `sim_2_1_1`.

Limits:
- Leaf outgroups only; rerooting on an internal node is not covered by this argument.
- Topology only: branch lengths and γ are dropped. NetCS writes neither.
- The file's own rooting is assumed valid (each `#H<n>` once inner, once leaf, the leaf
  not inside its own clade); `reroot_on` does not test it. All 14 real outputs with
  hybrids pass.
- Checked by reading outputs and by CmpNets (an already-rooted network scores the same
  after `reroot_on`), not against PhyloNetworks `rootatnode!`.

**Not deterministic.** NetCS's hybrid varies per run, and with it whether the input root is
valid. Repeat runs on one input (trees of blobs at TOB-QMC alpha 0.25, the only ones with
blobs of degree ≥ 5):

| Dataset | Runs | Rooted on `OUT` | Distinct outputs |
|---|---|---|---|
| `sim_1_1_1` (fixture) | 36 | 35 | 2 in 30 |
| `sim_2_1_1` (fixture) | 32 | 0 | 6 in 30 |
| two new datasets, real pipeline (k = 1, k = 2) | 10 | 0 | 9 roots |

So the root is mostly per dataset, not a coin flip; resume keeps the first success.

**Group estimate: none.** `network-score` scores the point estimate; `edges_added` = its
distinct `#H<n>` labels, 0 for a tree.

Rejected alternatives:
- Rerooting with Julia (`rootatnode!`, as SNaQ): `Bio.Phylo` suffices, no Julia dependency.
- Scoring a network not rooted on `OUT`: FN 0.67 / FP 0.58, against 0.32 / 0.32 rooted
  (alpha 0.25).
- Repeat-and-vote over runs: analysis, not inference.

## Scoring

`network-score` reads the point estimate, strips annotations and renumbers NetCS's 0-indexed
hybrids (`score_network`; CmpNets rejects `#H0`), then runs PhyloNet `CmpNets -m cluster`
against the true network. Tree scoring (RF) skips NetCS. `guide_tree` in
`network_scores.csv` is null. Unresolved blobs (degree < 5) are scored as written.

**A network not rooted on the dataset's outgroup is not scored:** its row has null rates,
status `ok` (`handle_network_score.is_rooted_on`: the outgroup is a leaf child of the root).
Cluster scoring is root-dependent; scored anyway, such networks gave FN 0.67 / FP 0.58,
against 0.32 / 0.32 rooted on `OUT` (alpha 0.25).

**Limit: a NetCS network with hybrids often cannot be rooted on `OUT`, so has no score.** On
our data (table above) three of four such datasets never were. Scored so far beyond that:
k = 0, the two default-alpha datasets with a kept 4-polytomy (FN 0.419 / FP 0.357;
FN 0.422 / FP 0.071). Analyses must count the null rows.

## Outputs

`<cond>/NETCS/networks/`, with `N` = the dataset stem:

| File | Writer | Content |
|---|---|---|
| `N.net` | `tree-qmc`, then `NetcsRunner.execute` | point estimate: rerooted on the outgroup, or as NetCS wrote it if it cannot be |

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
