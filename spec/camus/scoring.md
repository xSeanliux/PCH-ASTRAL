# CAMUS network scoring (future work)

Score an inferred level-1 network against the reference network, using **PhyloNet**.
Sibling to the tree RF scorer (`scripts/lib/inference/scoring.py`,
`pch experiment score`) — not a replacement.

`PLAN.md` PR 4 holds the design: the adapter, the CmpNets contract, the tasks. This file
holds the measurements behind it.

**Metric: `CmpNets -m cluster`**, FN and FP over soft-wired clusters — what the CAMUS
paper uses (§4.4). Not `CalGTProb` likelihood.

## Reference networks are contact networks

`net{h}-{t}.txt` is the base tree on line 1, then one line per contact event:

```
clade_a_newick ; clade_b_newick ; contact_time ; transmission_strength
```

From LingPhyloSimulator source:

| Question | Finding | Evidence |
|---|---|---|
| How are clades matched? | Exact string equality against the subtree's newick, without its branch length | `Network.java:310-321,487-496` |
| What is `contact_time`? | Distance from the root | `Network.java:29,312,262` |
| Is a contact directed? | No. Direction is a coin flip per character | `PolymorphicCharacter.java:129-130` |
| What does a transfer do? | Adds one donor state to the recipient's set; nothing is replaced | `PolymorphicCharacter.java:132-145` |
| What is `transmission_strength`? | Factor on the per-character borrowing probability | `PolymorphicCharacter.java:123` |

So a contact event is two contact edges, one per direction
(`docs/adr/0001-bidirectional-reference-networks.md`), and there is no inheritance
proportion to carry over.

## Reference networks are not all level-1

Over all 96 files in `data/base_networks/`, taking each contact as one cycle: 0/32 at
h=1, 14/32 at h=2, 26/32 at h=3 are not level-1 — 42%. With two contact edges per event,
every reference with h ≥ 1 is level ≥ 2.

CAMUS emits level-1 only, so it cannot reach these references at any k. That floor is a
property of the method's hypothesis space, not a measurement artefact.

## CmpNets across levels (measured, 7 taxa)

Level-1 estimates against level-2 and level-3 references. All runs exit 0.

| Reference vs estimate | `cluster` FN / FP | `tree` FN / FP |
|---|---|---|
| level-2 vs level-1, one correct edge | 0.25 / 0.0 | 0.4 / 0.4 |
| level-2 vs level-1, one right and one wrong | 0.25 / 0.25 | 0.8 / 0.8 |
| level-2 vs plain tree | 0.375 / 0.0 | 0.8 / 0.8 |
| level-3 vs level-1 | 0.4 / 0.0 | 2.0 / 2.0 |
| level-3 vs plain tree | 0.5 / 0.0 | 2.8 / 2.8 |
| level-2 vs itself | 0.0 / 0.0 | −8.9e-16 |

- **`cluster`** stays in [0, 1] and matches the cluster set difference computed by hand.
  Swapping the inputs swaps FN and FP.
- **`tree`** returns FN = FP, exceeds 1, grows with edge count, and goes slightly negative
  at zero. It is not an error rate. It is also exponential in edge count.

CmpNets has nine methods: `tree | tri | cluster | luay | rnbs | apd | normapd | wapd |
normwapd`. The last five need branch lengths or probabilities.

## Input shapes to avoid

| Shape | Result |
|---|---|
| Inheritance probabilities (`#H1:1.0::0.6`) | exit 1, `ExNewickException` |
| Mismatched taxon sets | `tree` exits 1; **`cluster` silently returns numbers** |
| Contact between sister lineages (3-cycle) | scores 0.0 against the plain tree: invisible |
| Doubled `;` after a newick | `missing END at ';'` |

Branch lengths, internal node labels, and differing hybrid labels are fine.

## The bidirectional reference (measured, 6 taxa)

Base tree `((((A,B),C),(D,E)),OUT)`, one contact event between B and C:

```
reference = ((((A,((B)#H2,#H1)),((C)#H1,#H2)),(D,E)),OUT);
```

| Estimate | `cluster` FN | FP |
|---|---|---|
| the reference itself | 0.0 | 0.0 |
| one contact edge, C → B | 0.167 | 0.0 |
| one contact edge, B → C | 0.167 | 0.0 |
| plain tree | 0.333 | 0.0 |

Both directions score alike, so no arbitrary choice leaks into the score.

## The paper's protocol

| | Paper |
|---|---|
| Reference networks | SiPhyNetwork, directed, filtered to level-1 (§4.2) |
| k scored | k = 1 for every method; "selecting the correct number of reticulations is non-trivial" (§4.6) |
| Scoring cost | over 5 hours for one 51-species network; scoring capped at ≤ 51 species |
| Inference | ASTRAL-IV guide tree rooted on the outgroup, gene-tree edges under 75% bootstrap collapsed, `camus -n 32 -q 2 -t 0.5` |

We score every k against undirected, partly non-level-1 references: outside what the paper
tested. Scoring runtime at 31 taxa and high k is unmeasured.
