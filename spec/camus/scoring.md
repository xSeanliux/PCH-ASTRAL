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
CmpNets net1 net2 -m cluster;
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

### Choosing the method: `cluster` (the paper's) vs `tree` (direction-invariant)

`CmpNets` has **nine** methods, not three — the full list from the class file is
`tree | tri | cluster | luay | rnbs | apd | normapd | wapd | normwapd`. The last five need
branch lengths/probabilities and error on topology-only input.

The CAMUS paper states: *"to assess phylogenetic network topology estimation error, we use
the cluster metric from PhyloNet's CmpNets command"* — so `-m cluster`, which prints
`The cluster-based distance between two networks: FN FP AVG`.

The tension is direction. Our contact events have no donor/recipient (§1), so any
direction-sensitive metric charges our arbitrary choice as method error. Measured on a pair
of networks differing *only* in which lineage of one contact event is the hybrid:

| method | direction-flip distance | discriminates (level-1 vs tree) |
|---|---|---|
| `tree` | **0.0** — fully invariant | 1.0 |
| `cluster` | 0.25 | 1.0 |
| `tri` | 0.817 | — |
| `luay` | 6.0 | — |

So `cluster` is direction-*sensitive* but far less than `tri`/`luay`. That 0.25 is one
differing cluster out of four on a 4-taxon network — coarse granularity at tiny scale; at
30 taxa one reticulation's worth of clusters is a much smaller fraction, so the artifact is
probably modest. **Measure it at realistic scale before committing.**

**Recommendation: report `-m cluster` as the primary metric, with `-m tree` as a control.**
`cluster` keeps our numbers comparable to the published CAMUS results, which matters for
work in the same line. `tree` is direction-invariant, so the gap between the two *is* the
direction artifact — that makes it a measurement rather than an unknown, and worth stating
in the paper. If the gap turns out large at 30 taxa, switch to `tree` and say why.

With a deterministic direction rule the artifact is systematic rather than random noise,
which is the better failure mode either way.

### Rejected: making the truth bidirectional by emitting two copies

The obvious fix for the direction problem is to represent each symmetric contact as *both*
directed reticulations (A→B and B→A). PhyloNet parses such a network fine (0.0 against
itself), but **it backfires**, and the FN/FP split shows exactly why:

| comparison | `cluster` FN | `cluster` FP |
|---|---|---|
| bidirectional truth vs a *correct* single-direction estimate | **0.43** | 0.00 |
| single-direction truth vs the same correct estimate | 0.00 | 0.00 |

A CAMUS network that recovered the contact event **perfectly** is charged 43% false
negatives — purely for missing the second copy it can never produce. FP is 0: the estimate
invents nothing. Under `-m tree` it's 0.5/0.5.

Two independent reasons it cannot work:

1. **It penalises a perfect answer**, and by far more (0.43) than the direction artifact it
   was meant to fix (0.25).
2. **It forces every truth to level ≥2.** The two copies share a cycle, so they land in one
   biconnected component. CAMUS only emits level-1, so *no* dataset would be reachable —
   including h=1, which is currently our clean condition.

The instinct is right, though: the truth *is* symmetric, and that should be reflected. The
fix belongs on the **scoring** side, not in the representation.

### Preferred fix: minimise over orientations

Score the estimate against **every orientation of the truth** (2^h networks; h ≤ 3, so at
most 8) and keep the best. An estimate matching any consistent orientation scores 0, which
is exactly the semantics an undirected contact event deserves.

- Keeps the truth level-1, so h=1 stays fully reachable.
- Keeps k = h, so the elbow's x-axis keeps its meaning.
- Stays on `-m cluster`, so numbers remain comparable to the published results.
- Costs ≤8 CmpNets calls per (dataset, guide_tree, k) — negligible beside inference.

`-m tree` remains the cheaper alternative: invariant by construction, one call, no
enumeration — at the cost of diverging from the paper's metric.

Under either metric the adapter's three choices stay cheap: **γ** is ignored by both
(topology only), and **`contact_time`** changes topology only when two contacts insert on
the same branch — sort those by time. Only **direction** carries any weight, and only under
`cluster`.

Caveat: `-m tree` enumerates displayed trees (2^r), so it is exponential in reticulation
count. Fine for our truths (h ≤ 3 → 8 trees) but CAMUS families run to whatever k the DP
reached. **Verify runtime at realistic scale (30 taxa, high k) before the first big sweep.**

### The rest of the paper's protocol

Inference (supplementary §2, §4): ASTRAL-IV constraint tree rooted on the outgroup,
gene-tree edges below 75% bootstrap collapsed, then
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
