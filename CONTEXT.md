# PCH-ASTRAL

Infers linguistic phylogenies, as trees and as networks, from polymorphic character matrices.

## Language

### Reference (simulated truth)

**Base tree**:
The tree underlying a reference network, before any contact events.
_Avoid_: Model tree, true tree

**Contact event**:
An undirected episode of borrowing between two lineages in a reference network. Neither lineage is donor or recipient.
_Avoid_: Horizontal edge, reticulation edge

**Contact edge**:
One directed edge outside the tree, from a donor lineage to a recipient lineage. A reference network encodes each contact event as two contact edges, one per direction.
_Avoid_: Reticulation, hybrid edge, lateral edge (use "reticulation" only when quoting CAMUS or PhyloNet)

**h**:
The number of contact events in a reference network. `h = 0` is a base tree alone.
_Avoid_: A, horizontal edges

**Outgroup**:
A taxon known to be sister to all others, used to root unrooted trees. Labelled `OUT`. Kept in every stage, never pruned.
_Avoid_: OG

### Inference

**Guide tree**:
The rooted binary tree a network method starts from and must contain.
_Avoid_: Constraint tree (CAMUS's own term; use only when quoting it)

**k**:
The number of contact edges a network method added to the guide tree.
_Avoid_: Number of branches

**Tree of blobs**:
A network's tree with each blob (cycle-bearing region) contracted to one node; TOB-QMC's estimate. Unrooted, may have polytomies.
_Avoid_: TOB (except as TOB-QMC)

**Network family**:
All networks from one inference run, one per k, starting at k = 0 (the guide tree).
_Avoid_: Point estimate, per-k output
