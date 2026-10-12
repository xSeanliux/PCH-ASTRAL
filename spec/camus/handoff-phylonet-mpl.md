# Handoff: PhyloNet-MPL(FT)

As of 2026-10-11. PR #51 (`phylonet-mpl` → `main`), mergeable, checks green. Method doc:
`docs/method_docs/phylonet_mpl/README.md` (read it first). Wider network context:
`spec/camus/HANDOFF.md`.

## State

- Rebased on `main` (after #50 SNaQ, #52–#54 network contract, #47 TOB-QMC).
- Config: `phylonet_mpl: {guide_trees: [...], procs: N}`. `procs` is excluded from
  `config_hash`, as `snaq.procs`. Guides: `PHYLONET_MPL_GUIDE_TREES` = `pch_astral3`,
  `pch_wastral`, `true_tree`, `ga`.
- Output: `PHYLONET_MPL/networks/N.{result,net,family.csv}`; family CSV extra column
  `log_probability`; `is_best` = first network.
- Review threads on #51 all answered; none resolved (the user resolves them).
- #60 (SNaQ rejects `tob_qmc`) edits the same `docs/ARCHITECTURE.md` guide-tree sentence:
  whichever merges second keeps both.

## Decisions (agreed with the user)

| Decision | Where |
|---|---|
| Every PCH-W quartet is rooted by the guide (1\|3 → that taxon's pendant edge; 2\|2 → central edge). OUT-only rooting kept ~13% of the weight. | `root_quartets`, `scripts/py/phylonet_mpl_nexus.py` |
| One gene tree line per rooted quartet, weighted: `Tree gtN = [&W w] ...`. PhyloNet sums weights per topology, so this equals repetition (6-taxon test). | `build_nexus` |
| `tob_qmc` is not a guide: a tree of blobs is input to BROOQS (#57) / NetCS (#58), not a species tree. | `guide_tree.py` |
| `-fs` not fixing the tree is documented, not investigated further. | method doc, "Fixed tree" |

## Findings

- PhyloNet reads triples from each gene tree's Newick root, never rerooting
  (`computeTripleFrequenciesFromSingleGT`): rooting quartets is required.
- `-fs` does not keep the start tree in PhyloNet 3.8.5, with or without branch lengths,
  though it selects `treeAugmentInferNetworkMPL`. Treat "FT" as "start tree".
- Branch lengths: gene trees are topology only; start tree has none; output lengths are
  fitted to PCH-W weights, not interpretable, stripped at scoring.
- Defaults (bytecode): 10 runs, 100 failures in a row, no examination cap. No time cap.

## Next

1. Run `experiments/phylonet_mpl_smoke` (30 taxa + OUT, h = 1, 2) and record runtime in the
   method doc. Earlier 26-taxon run (voided) took >10.5 h with OUT-only quartets.
2. Add a wall-clock cap like SNaQ's 12 h `perl alarm` if runs hang.
3. Merge #51 once the user approves.

## Gotchas

- `source scripts/sh/env.sh` before tests; unset `FORCE_COLOR`.
- PhyloNet writes `logfile.txt` (~150 MB/h) in its cwd: `runPhyloNetMPL.sh` links it to
  `/dev/null`.
- Only base models in `data/` are valid; never hand-prune models.
- k = the true contact count: an oracle setting.
