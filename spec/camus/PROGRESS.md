# CAMUS — progress

As of 2026-09-30, PR 4 built. Plan of record: `PLAN.md`. Terms: `CONTEXT.md`. Next agent: `HANDOFF.md`.

## Goal

CAMUS runs end to end on `experiments/camus_smoke` and raw network scores land on disk.
Analysis, figures, comparison methods, quartet-filter knobs and rooting-accuracy
measurement are deferred on purpose.

## PR stack

```
main ← #32 ga-nexus-labels ← #33 outgroup-simulation
main ← #31 camus-install ← #34 camus-run ← #35 camus-registry ← camus-scoring/{adapter,scorer,cli}
```

Merge order: #32, #33, #31, #34, #35, then the `camus-scoring` stack bottom to top. Each
PR's body carries its own verification.

| PR | Branch | Built | State |
|---|---|---|---|
| #31 | `camus-install` | wiring; `InferenceMethod` → `TreeInferenceMethod` / `NetworkInferenceMethod`; `TreeRunner` / `NetworkRunner`; `guide_trees` set fans out to one run per guide | open, review comments addressed |
| #32 | `ga-nexus-labels` | GA NEXUS writer labels rows by taxon name, not position | open |
| #33 | `outgroup-simulation` | `simulation.outgroup: OUT`; graft with contact-time shift; registry points at copies; base trees always written; graft recorded in `model_graph_registry.csv` | open |
| #34 | `camus-run` | real `runCAMUS.sh`; `scripts/py/guide_tree.py` resolves and roots the guide; CAMUS pinned v1.0.2 | open |
| #35 | `camus-registry` | `camus_registry.py`: `write_family`, `compact`; ingest before the inference row; compaction local and SLURM | open |
| PR 4 | `camus-scoring/*` (gh-stack, 3 layers) | `network_format.py` adapter; `network_score` + `resolve_reference_network`; `pch experiment network-score` → `network_scores.csv` | built, not pushed |

## What works, measured

`experiments/camus_smoke` (outgroup `OUT`, h = 1 and 2, 2 replicas, 31 taxa, 80
characters), laptop, ~6.5 min for simulation + MP4 + GA + ASTRAL3 + wASTRAL + CAMUS:

- 28/28 runs ok; `astral3`, `wastral`, `true_tree` guides all rooted with `OUT` alone at
  the root.
- 12 network families, k from 0 to 4–6; CAMUS ~3.5 s per run.
- `camus_registry.csv`: 72 rows, no null cells; rerun skips everything, registry
  unchanged.
- GA runs clean with `OUT` present (the #32 fix, end to end).
- `network_scores.csv`: 72/72 `ok`, 0.21–0.43 s per CmpNets call, 18 s total; the 2 h
  timeout is far from binding at 31 taxa, k ≤ 6. `true_tree` k = 0 scores FP 0, FN 2/31
  at h = 1. Rerun is a no-op.

Facts established along the way, all verified against source or by running:

| Fact | Where recorded |
|---|---|
| Contact times count from the root; graft must shift them (0 vs 208 misplaced of 384) | `outgroup.md`, #33 body |
| CAMUS filters quartets by default (`-q 2 -t 0.5`); weights reach it through the filter | `inference.md`, `PLAN.md` |
| CAMUS v1.0.1 lacks fixes for k ≥ 2; pinned v1.0.2 | `install_camus.sh` |
| TREE-QMC can emit polytomies → `w_tree_qmc` not an allowed guide | `inference.md` |
| CmpNets `-m cluster` sound across levels; `-m tree` is not an error rate | `scoring.md` |
| Inheritance probabilities crash CmpNets; networks go in topology-only | `scoring.md` |
| Mismatched taxon sets return numbers silently under `cluster` | `scoring.md` |
| Reference encodes each contact event as two contact edges | `docs/adr/0001-*` |
| Bidirectional reference vs single-direction estimate: FN 0.167, plain tree 0.333 (6 taxa) | `scoring.md` |
| Paper scores k = 1 only, level-1 truths only, over 5 h for one 51-species network | `scoring.md` |

## Remaining

Push the `camus-scoring` stack and open its PRs. Plan of record: `plans/pr4-scoring.md`.

## Follow-ups, deliberately not started

- `experiments/camus_study` on the cluster.
- Analysis: k vs FN/FP, family length distribution, stratifying by reference level;
  carry the last network forward past a short family.
- Rooting accuracy: does the ingroup root split match the base tree's?
- Quartet filter knobs (`-t`, `-q`) in `CamusConfig`; `-q 0` as an ablation.
- Minimum over single-direction orientations, from stored newicks.
- Comparison methods: PhyloNet-MPL, SNaQ (`benchmarks.md`).
- How many reference contact events join sister lineages (invisible to `cluster`).
- `experiment status` for SLURM plans one CAMUS job per condition covering all guides.
- Pre-existing `ruff` issues in untouched files (`test_bipartitions.py` unused imports,
  a notebook and a few tests unformatted).
