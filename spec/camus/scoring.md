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

Direction reversed would give plausible, wrong scores. Needs a round-trip test on a
hand-built case whose answer is known by inspection.

### 2. 42% of the reference networks are not level-1

Measured over all 96 files in `data/base_networks/` (cycle = tree path between the two
contacting clades; level-1 breaks when two cycles share an edge):

| h | total | not level-1 |
|---|---|---|
| 1 | 32 | **0** |
| 2 | 32 | 14 (44%) |
| 3 | 32 | 26 (81%) |

CAMUS only emits level-1 networks, so for those 40 references **the truth is outside its
hypothesis space** and FN cannot reach 0 regardless of method quality. Scoring must
therefore record `is_level_1` (stored per model network in `model_graph_registry.csv`) and
the analysis must stratify on it — otherwise "CAMUS failed" and "CAMUS could not possibly
succeed" are averaged together. h=1 is the clean primary condition.

Also confirm PhyloNet's comparison command **accepts a non-level-1 reference** at all. If
it doesn't, the h=2/h=3 strata need a different metric.

## Intended flow

1. Read each inferred network (`network_newick` from `camus_registry.csv`) and the truth
   (`net{h}-{t}.txt`, via the adapter above).
2. Emit a NEXUS command file, run `java -jar bin/PhyloNet.jar`, parse stdout.
3. Write `network_scores.csv` keyed on (`dataset_id`, `guide_tree`, `k`), joining back to
   `camus_registry.csv` (see `registry.md`). Feeds the inferred-edges vs FN elbow.

## Open questions

- The exact PhyloNet command and its stdout contract — **verify before writing the
  wrapper**, don't assume `cmpnets`.
- Rooting/label reconciliation between CAMUS output and the true network. Both carry the
  outgroup (it is never pruned — see `outgroup.md`), so the taxon sets should already
  match; confirm PhyloNet agrees.
