# CAMUS network scoring (future work)

Score an inferred level-1 network against the truth, using **PhyloNet** — the
benchmark the paper uses. Parallels the tree RF scorer
(`scripts/lib/inference/scoring.py`, `pch experiment score`).

## PhyloNet

- `java -jar bin/PhyloNet.jar cmd.nex` — driven by a NEXUS command block.
- `CalGTProb` computes the (pseudo-)likelihood of gene trees given a network;
  3.8.5 added pseudo-likelihood scoring. This is the primary score.
- Command reference: PhyloNet wiki ("List of PhyloNet Commands").

## Intended flow

1. Read each inferred network (a `network_newick` row from `camus_registry.csv`) +
   the truth (model network `net{edges}-{tree}.txt`) + gene trees.
2. Emit a NEXUS command file (a `scoring/` R or Python template) invoking the
   chosen PhyloNet command.
3. `java -jar bin/PhyloNet.jar` → parse the score out of stdout.
4. Write to `network_scores.csv` keyed by (`dataset_id`, `guide_tree`, `k`) —
   one score per network in the family — joining back to `camus_registry.csv`
   (see `registry.md`). This feeds the inferred-edges (k) vs FN-error elbow.

## Metrics to settle

- Likelihood / pseudo-likelihood via `CalGTProb` (rank inferred networks).
- Topological network distance to the true network vs. inferred (analog of
  RF for networks) — check what the btag245 supplement reports.
- FN/FP of reticulation edges.

## Open questions

- Rooting/label reconciliation between CAMUS output and the true network before
  PhyloNet will accept them.
