---
status: accepted
---

# Reference networks encode each contact event as two contact edges

Our reference networks hold undirected contact events, but PhyloNet's `CmpNets` scores
directed networks. We encode each contact event between lineages x and y as two contact
edges, x→y and y→x, because that is what the simulator does: it picks the direction by
coin flip per character (`PolymorphicCharacter.java:129-130`), so both directions occur.

## Considered options

- **One arbitrary direction.** Charges the arbitrary choice as method error.
- **Minimise over all 2^h orientations.** Lets a perfect estimate score 0, but the truth
  it scores against is not what generated the data. Still computable later: the network
  family registry keeps every inferred newick.

## Consequences

- No estimate from a level-1 method can score 0 when h ≥ 1. Both contact edges of one
  event share a cycle, so the reference is level ≥ 2 and a level-1 network holds at most
  one of them. On a 6-taxon case a perfect single-direction estimate scores FN 0.17, the
  plain tree 0.33.
- The floor is a limit of the method's hypothesis space, the same kind as the floor on
  references that were never level-1.
- A reference with h contact events has 2h contact edges. Compare k against h, not 2h.
- The donor point sits above the hybrid point on both branches; the reverse order on
  both makes a cycle.
