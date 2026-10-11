# Handoff

As of 2026-10-10. CAMUS runs end to end on `main`. Two more network methods (SNaQ #50,
PhyloNet-MPL #51, both part of #43) are open, mergeable, CI green, and share one network
output contract.

## State

- Merged: #33 outgroup graft, #31 wiring, #34 `runCAMUS.sh` and guide trees, #36 contact network
  adapter, #37 network scoring (with #38), #48 `bipartition_strategies: []`, #49 this handoff.
- Closed: #35 `camus_registry`. Each network run's family CSV (`N.family.csv`) is its
  `group_estimate_path` in `inference_registry`; `handle_network_score.read_families` reads them
  from there.
- Open: **#50** `snaq` (SNaQ, plus the shared network contract below). **#51** `phylonet-mpl`
  (PhyloNet-MPL(FT); carries an identical copy of the shared files, so it merges cleanly on its
  own). Whichever merges second re-conflicts in docs (`MIGRATIONS.md`, `SCHEMAS.md`,
  `SCRIPT_CONTRACTS.md`), `test_handle_network_score.py` and method registration
  (`experiment.py`, `runners/__init__.py`, `methods.py`): keep both sides.
- Open: #47 TOB-QMC (separate). Issues #43–#46: other network methods; #40: outgroup length.

## Network output contract (#50, #51)

Every network method writes `<cond>/<METHOD>/networks/N.family.csv`, converted from the tool's
raw output (kept beside it) by its `Runner.execute` (e.g. `camus_to_family`, `snaq_to_family`):

| Column | Meaning |
|---|---|
| `edges_added` | Hybrid count. |
| `network_newick` | As the tool wrote it; `score_network` strips lengths and γ. |
| `is_best` | The method's own pick by its own objective, never by accuracy: at most one per `edges_added`. Only these rows are scored. |
| extras | CAMUS `quartet_satisfied_percent`; SNaQ `neg_loglik`; MPL `log_probability`. |

CAMUS marks every k `is_best` (each is its own optimum). Network point estimates are
`point_estimate_newick`; tree scoring skips network methods. `guide_tree` in `network_scores` is
from `method_config_json` for CAMUS and SNaQ (`pch_wastral` in the smoke test, as in the CAMUS
paper); `pch_wastral` for MPL (its fixed tree). Schema:
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
ask James Willson. Smoke (11 taxa) FN/FP: sim_1 0.25/0.36 (row 0), sim_2 0.44/0.33 (row 1; was
0.83/0.79 with SNaQ's root).

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

- `experiments/snaq_smoke` (#50): 11 taxa, h = 1 and 2. SNaQ is ~20 min per dataset at 11–12
  taxa and did not finish in 65 min at 31; `PCH_SNAQ_PROCS=10` runs the 10 runs in parallel.
- `experiments/phylonet_mpl_26` (#51): 26 taxa, MPL(FT) (`-fs`), h = 1 and 2. Running since
  2026-10-10; >6 h wall on the first dataset (the laptop slept). No result yet.
- Both use a local, git-ignored `data/` of base networks pruned from `data/base_networks`; don't
  commit it. The specs say how it was made.

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

1. Finish the MPL 26-taxon run; merge #50, then #51 (re-resolve docs conflicts).
2. Refresh #50's PR body (contract, rooting rule, hmax wording).
3. Ask James how the paper rooted SNaQ; revisit step 2 if needed.
4. Report the simulator bug; add a caveat to CLAUDE.md ("seeds are deterministic").
5. `experiments/camus_study` on the cluster.
6. Follow-ups, not started: 12 h cap for MPL; per-runner `read_group_estimate` if converters
   multiply; k vs FN/FP analysis; CAMUS `-t`/`-q` knobs; CLI support for real datasets.
