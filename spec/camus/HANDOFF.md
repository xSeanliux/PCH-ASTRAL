# Handoff

As of 2026-10-06. CAMUS runs end to end on `main`: simulate → MP4/GA/ASTRAL3 → CAMUS → RF and
network scoring. The phase goal ("raw network scores on disk") is met.

## State

- Merged: #33 outgroup graft, #31 wiring, #34 `runCAMUS.sh` and guide trees, #36 contact network
  adapter, #37 network scoring (with #38 folded in).
- Closed: #35 `camus_registry`. Each CAMUS run's per-k CSV is its `group_estimate_path` in
  `inference_registry`; `handle_network_score.read_families` reads them from there.
- Open: **#48** `bipartition_strategies: []` means no extra trees (heuristic ASTRAL on the quartets
  alone). Same `config_hash` as the old MP4 + GA default; see `docs/MIGRATIONS.md`.
- Open: #47 TOB-QMC (separate work). Issues #43–#46: other network methods; #40: outgroup length.

## Smoke run

`experiments/camus_e2e`: 2 model trees, 30 taxa + `OUT`, h = 1 and 2, one condition, 1 replica,
ASTRAL3 with `[]` and CAMUS on `pch_astral3` and `true_tree`. Needs #48. About 10 min on a
laptop; set `PCH_ASTRAL_XMX=8g` (4g runs out of heap at 150k quartets).

```bash
S=experiments/camus_e2e/experiment_specification.yaml
python3 -m scripts.py.cli.main simulation $S
python3 -m scripts.py.cli.main experiment inference $S
python3 -m scripts.py.cli.main experiment score $S
python3 -m scripts.py.cli.main experiment network-score $S
```

Last result (2026-10-06): 12/12 runs and 59/59 network scores `ok`; `true_tree` with 0 edges
added scores FP 0 at every h; reruns change nothing.

## Gotchas

- **The simulator is not reproducible for networks.** `LingPhyloSimulator.jar` with
  `--network-input-file` gives different data for the same `--seed`; with `--tree` it is
  stable. h ≥ 1 datasets cannot be regenerated from their seed. Not yet reported upstream.
- `FORCE_COLOR` set in the shell breaks `test_handle_status` (colour codes in the output). Run
  tests with it unset.
- `network_scores.csv` never retries a `failed` or `timeout` row; delete the row to rescore.
- `spec/camus/{registry,README,inference,benchmarks,PLAN}.md` still describe `camus_registry`.

## Next

1. Merge #48.
2. Report the simulator bug; add a caveat to CLAUDE.md ("seeds are deterministic").
3. `experiments/camus_study` on the cluster.
4. Follow-ups, deliberately not started: k vs FN/FP analysis, rooting accuracy, CAMUS `-t`/`-q`
   knobs, other network methods (#43–#46), CLI support for real datasets.
