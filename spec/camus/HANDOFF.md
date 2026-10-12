# Handoff

As of 2026-10-11. CAMUS and SNaQ (#50) run end to end on `main`; PhyloNet-MPL(FT) (#51, part
of #43) is open. All share one network output contract.

## State

- Merged: #33 outgroup graft, #31 wiring, #34 `runCAMUS.sh` and guide trees, #36 contact network
  adapter, #37 network scoring (with #38), #48 `bipartition_strategies: []`, #49 this handoff.
- Closed: #35 `camus_registry`. Each network run's family CSV (`N.family.csv`) is its
  `group_estimate_path` in `inference_registry`; `handle_network_score.read_families` reads them
  from there.
- Merged: #52 model graph, #53 family CSV, #54 `GuidedNetworkConfig`, #50 SNaQ.
- Merged: #47 TOB-QMC, a *tree* method: a tree of blobs is not a level-1 network, only the input
  BROOQS (#57) and NetCS (#58) expand into one. Not a valid guide tree.
- Open: #51 PhyloNet-MPL(FT). Issues #43–#46: other network methods; #40: outgroup length.

## Network output contract (#50, #51)

Every network method writes `<cond>/<METHOD>/networks/N.family.csv`, converted from the tool's
raw output (kept beside it) by its `Runner.execute` (e.g. `camus_to_family`, `snaq_to_family`, `phylonet_mpl_to_family`):

| Column | Meaning |
|---|---|
| `edges_added` | Hybrid count. |
| `network_newick` | As the tool wrote it; `score_network` strips lengths and γ. |
| `is_best` | The method's own pick by its own objective, never by accuracy: at most one per `edges_added`. Only these rows are scored. |
| extras | CAMUS `quartet_satisfied_percent`; SNaQ `neg_loglik`; MPL `log_probability`. |

CAMUS marks every k `is_best` (each is its own optimum). Network point estimates are
`point_estimate_newick`; tree scoring skips network methods. `guide_tree` in `network_scores` is
from `method_config_json` (`pch_wastral` in the smoke tests, as in the CAMUS paper). Schema:
`NETWORK_FAMILY_SCHEMA` in `scripts/py/cli/schemata.py`; details in `docs/SCHEMAS.md`.

## SNaQ rooting

SNaQ fits unrooted quartet CFs, so its network is semi-directed: no identifiable root. CmpNets
`-m cluster` is root-dependent, so SNaQ's networks must be rooted on `OUT`. If SNaQ puts `OUT`
below a hybrid, rooting there would reverse hybrid edges (`RootMismatch`). Rule (#50, 0ceca0d):

1. SNaQ → best plus `.networks` alternatives (same undirected network, hybrid moved), by `-loglik`.
2. `is_best` = lowest `-loglik` network consistent with `OUT` (`rootatnode!` succeeds); none → no
   point estimate, nothing scored, run still `ok` (`Runner.is_point_estimate_optional`).
3. Point estimate = it, rerooted on `OUT` (`.net`; `.choice` holds the row or `none`).
4. CmpNets against the true network.

Rejected: scoring SNaQ's arbitrary root (inflated error); moving hybrids ourselves
(`hybridatnode!`, c205b43); re-orienting all edges away from `OUT` (undefined on odd cycles,
discards SNaQ's hybrids). The CAMUS paper and its gists don't say how SNaQ was rooted for scoring;
ask James Willson. The earlier smoke FN/FP (sim_1 0.25/0.36, sim_2 0.44/0.33; 0.83/0.79 with
SNaQ's root) came from hand-pruned 11-taxon models and are void; rerun at 30 taxa.

## Smoke runs

`experiments/camus_e2e`: 2 model trees, 30 taxa + `OUT`, h = 1 and 2, ASTRAL3 with `[]`, CAMUS on
`pch_astral3` and `true_tree`. About 10 min; set `PCH_ASTRAL_XMX=8g`.

```bash
S=experiments/camus_e2e/experiment_specification.yaml
python3 -m scripts.py.cli.main simulation $S
python3 -m scripts.py.cli.main experiment inference $S
python3 -m scripts.py.cli.main experiment score $S
python3 -m scripts.py.cli.main experiment network-score $S
```

- `experiments/snaq_smoke` (#50): 30 taxa + `OUT`, h = 1 and 2. SNaQ did not finish in 65 min
  at 31 leaves; `snaq.procs: 10` runs the 10 runs in parallel. Not yet run at this size.
- `experiments/phylonet_mpl_smoke` (#51): 30 taxa + `OUT`, h = 1 and 2. A 26-taxon run (since
  deleted, hand-pruned) was stopped after 10.5 h. PhyloNet defaults: 10 runs (`-x`), no examination
  cap, a run stops after 100 failed proposals in a row. `-fs` uses the fixed-tree search only if
  the start network parses; that run explored 2,107 backbone trees, so the tree was not fixed.
- Only the base models in `data/` are valid inputs: there is no tree simulation, and
  `simulation.n_taxa` is not read (the base tree file sets the taxa). Don't hand-prune models.

## Gotchas

- **The simulator is not reproducible for networks.** `LingPhyloSimulator.jar` with
  `--network-input-file` gives different data for the same `--seed`; with `--tree` it is
  stable. Not yet reported upstream.
- `FORCE_COLOR` set in the shell breaks `test_handle_status`. Run tests with it unset.
- `network_scores.csv` never retries a `failed` or `timeout` row; delete the row to rescore.
- Old registries: see `docs/MIGRATIONS.md` (family CSVs; SNaQ `--choose`).
- SNaQ caps at 12 h (`perl alarm`); `runPhyloNetMPL.sh` has no cap.
- hmax = the true reticulation count is an oracle setting; the CAMUS paper did this only in its
  one-reticulation experiments.
- `spec/camus/{registry,README,inference,benchmarks,PLAN}.md` still describe `camus_registry`.

## Next

1. Rerun `snaq_smoke` and `phylonet_mpl_smoke` at 30 taxa; find why `-fs` did not fix MPL's tree; merge #51.
2. Refresh #50's PR body (contract, rooting rule, hmax wording).
3. Ask James how the paper rooted SNaQ; revisit step 2 if needed.
4. Report the simulator bug; add a caveat to CLAUDE.md ("seeds are deterministic").
5. `experiments/camus_study` on the cluster.
6. Follow-ups, not started: 12 h cap for MPL; per-runner `read_group_estimate` if converters
   multiply; k vs FN/FP analysis; CAMUS `-t`/`-q` knobs; CLI support for real datasets.
