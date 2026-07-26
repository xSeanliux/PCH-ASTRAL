# CAMUS network scoring (future work)

Score an inferred level-1 network against the true network, using **PhyloNet**.
Sibling to the tree RF scorer (`scripts/lib/inference/scoring.py`,
`pch experiment score`) — not a replacement. See `PLAN.md` PR 4 for the full task
breakdown.

**Metric decision: topological distance to the true network** (FN/FP), so the numbers are
comparable in kind to `scores.csv`. Not `CalGTProb` likelihood — the elbow's y-axis is an
error rate. Likelihood stays available as a later addition if model selection over k is
wanted.

## Two things that make this harder than the tree scorer

### 1. Our reference "networks" are contact networks

`net{h}-{t}.txt` is the base tree on line 1, then one line per horizontal edge:

```
clade_a_newick ; clade_b_newick ; contact_time ; transmission_strength
```

The two clade fields are **symmetric** — the two clades that contact each other — with no
donor/recipient direction. A clade is either a bare leaf label (`t26`) or a full subtree
newick. Confirmed against LingPhyloSimulator `Main/Network.java`: `readFromFile` splits on
`;`, asserts 4 fields, parses time and strength; `writeNetwork` emits
`newick1;newick2;edge.left.Time;edge.transmission_strength`.

PhyloNet takes **Rich/extended newick**, where reticulations are *directed*: a hybrid node
`#H1` with two parents and an inheritance probability γ. So an adapter is required, and it
must make three choices explicitly rather than by accident:

1. **Direction** — undirected contact → directed hybrid edge. One direction (discards half
   the event) or both (two reticulations per contact, changing k and the level, which makes
   comparison against a k-edge CAMUS network incoherent).
2. **γ** — `transmission_strength` is plausibly an inheritance proportion but isn't defined
   as one. Verify against how the simulator consumes it.
3. **Hybrid node placement** — `contact_time` positions the event on both branches; Rich
   newick encodes position topologically.

### The adapter, concretely

Given the base tree `T` and one contact line `cladeA;cladeB;time;strength`:

1. **Locate both clades in `T` by taxon set** — a field is either a bare leaf label
   (`t26`) or a full subtree newick, so parse out its taxa and match the clade whose
   terminal set is equal. (Same lookup the level-1 check uses.)
2. **Pick donor `D` and recipient `R`** by the deterministic rule. Low-stakes — see the
   metric section.
3. **Rewrite two places** for contact *i*:
   - at `R`: `R_subtree:len` → `(R_subtree:len)#H{i}:len::{1-strength}`
   - on `D`'s branch: `D_subtree:dlen` → `(D_subtree:dlen,#H{i}:0::{strength})`
4. **If several contacts insert on the same branch**, order them by `contact_time`.
5. Emit the Rich newick.

Verification: a hand-built case whose answer is obvious by inspection, plus an assertion
that both direction choices score `0.0` against each other under `-m tree` — that test is
what keeps the direction rule from silently mattering later.

### 2. Reference networks are not all level-1 — but that's fine

Measured over all 96 files in `data/base_networks/` (cycle = tree path between the two
contacting clades; level-1 breaks when two cycles share an edge): 0/32 at h=1, 14/32 at
h=2, 26/32 at h=3 are **not** level-1 — 42% overall.

**PhyloNet handles this** — `CmpNets` accepts arbitrary-level networks (verified below), so
the comparison is well-posed either way. No flag is stored: CAMUS emits level-1 by
definition, and a reference's level is a pure function of a file we already have, so it can
be computed on demand if an analysis ever wants to stratify on it.

The one thing to remember when reading results: CAMUS cannot represent a non-level-1 truth
at any k, so those datasets have a nonzero error floor. That's a property of the method's
hypothesis space, not a measurement artefact. h=1 is the only condition where every
reference is level-1.

## PhyloNet contract (verified against bin/PhyloNet.jar 3.8.5)

```
#NEXUS
BEGIN NETWORKS;
Network net1 = ((((B)#H1,C),(#H1,D)),A);
Network net2 = (((A,B),C),D);
END;
BEGIN PHYLONET;
CmpNets net1 net2 -m tree;
END;
```

- **Arguments are bare identifiers** defined in a `NETWORKS` block — not inline newicks
  (CmpNets tries to parse those as newick), not brace-wrapped sets.
- **The newick's own trailing `;` is the statement terminator.** Writing
  `Network net1 = <newick>;` where the newick already ends in `;` produces a doubled `;`
  and a misleading `missing END at ';'` error. This costs an hour if you don't know it.
- **Methods:** `tree`, `tri`, `luay` (anything else → `Unknown method`).
- **Output**, parsed from stdout:
  - `tree` / `tri` → `The {tree|tripartition}-based distance between two networks: FN FP AVG`
  - `luay` → `The Luay's distance between two networks: N` (single number)
- **Argument order is FN/FP order.** Swapping the two networks swaps the first two numbers
  (`0.8 1.0` ↔ `1.0 0.8`), so **net1 = reference/truth, net2 = estimate** — same convention
  as `RFScorer.R`. Getting this backwards silently inverts FN and FP.
- **Arbitrary level works:** a level-2 network compared against itself returns `0.0` under
  all three methods.
- `-m tree` additionally requires identical leaf sets (`Trees must have identical leaf
  sets`); `tri` and `luay` tolerate mismatches. Ours always match (same dataset, outgroup
  never pruned), so `-m tree`'s check is a free safety net rather than an obstacle.

### Use `-m tree` — it is the only direction-invariant option

Measured, and it is the single most important fact for this pipeline. Take one contact
event between two lineages, build the two networks that differ *only* in which lineage is
called the hybrid, and compare them:

| method | distance between the two directions |
|---|---|
| `tree` | **0.0 0.0 0.0** — invariant |
| `tri` | 0.8 0.833 0.817 |
| `luay` | 6.0 |

Our contact events **have no direction** (§1). So under `tri` or `luay` we would be
measuring our own arbitrary donor/recipient choice, not method accuracy — a coin flip per
reticulation, scored as error. `-m tree` compares the sets of displayed trees, which are
identical either way, so it measures what we actually mean.

This also **de-risks the adapter's three choices**, which were the scary part:

- **Direction** — no longer load-bearing. Pick a deterministic rule (e.g. the
  lexicographically smaller taxon set is the donor), document it, move on.
- **γ** — affects probabilities, not topology; a topology metric ignores it. Set
  `γ_minor = transmission_strength` for tidiness.
- **`contact_time`** — a branch has no internal structure, so *where* on the branch the
  hybrid attaches does not change the topology. It matters in exactly one case: when two
  contacts insert on the **same** branch, their relative order does change the topology.
  Sort insertions on a shared branch by `contact_time`.

Caveat: `-m tree` enumerates displayed trees (2^r for r reticulations), so it is
exponential in reticulation count. Fine for our truths (h ≤ 3 → 8 trees) but CAMUS's family
runs to whatever k the DP reached. **Verify runtime at realistic scale (30 taxa, high k)
before the first big sweep**, and cap k if needed.

### What the CAMUS paper uses, and why we differ

The paper reports a "cluster metric error rate" — the **hardwired cluster distance**:
extract each network's hardwired clusters (the leaves reachable below each edge), then
count clusters present in one network but not the other. FN/FP fall out directly.

That is *not* one of CmpNets' three methods, so they used their own code or
PhyloNetworks.jl's `hardwiredClusterDistance`, not PhyloNet, for scoring. PhyloNet in their
pipeline is the *competing inference method* (PhyloNet-MPL), not the scorer.

**Their metric is direction-dependent** (a "cluster below an edge" presupposes directed
edges), and that is fine for them: their truths come from SiPhyNetwork, which generates
properly directed reticulation networks. Ours are undirected contact events. So we should
not copy their metric — the difference is in our simulation model, not in our standards.

Their protocol, for the record (supplementary §2, §4): ASTRAL-IV constraint tree rooted on
the outgroup, gene-tree edges below 75% bootstrap collapsed, then
`camus -n 32 -q 2 -t $threshold -o $output $const_tree $gene_trees`, with t = 0.5 chosen on
simulated data (Figure S2) and t = 0.8 additionally explored on the empirical avian dataset
because its gene trees had ~25% average branch support.

## Intended flow

1. Read each inferred network (`network_newick` from `camus_registry.csv`) and the truth
   (`net{h}-{t}.txt`, via the adapter above).
2. Emit the NEXUS above into a `NamedTemporaryFile`, run `java -jar bin/PhyloNet.jar`,
   parse the `distance between two networks:` line.
3. Write `network_scores.csv` keyed on (`dataset_id`, `guide_tree`, `k`), joining back to
   `camus_registry.csv` (see `registry.md`). Feeds the inferred-edges vs FN elbow.

## Open questions

- Which of `tri` / `tree` best matches the "cluster metric error rate" the CAMUS paper
  reports. Both give FN/FP; pick one and state it.
- The adapter's three choices (direction, γ, hybrid placement) — see above.
