# CAMUS network registry (future work)

CAMUS does **not** produce one point estimate. For a guide tree `T`, it emits a
*family* of networks `N_1, …, N_m`, where `N_k` is the optimal network
containing `T` under exactly `k` added reticulation edges (`m` = the max
edges the search reaches). All k are kept — the whole point is to sweep k and
find where error stops improving.

The tree `inference_registry.csv` keys one `point_estimate_newick` per (dataset,
method, config), so it **cannot** hold this. CAMUS gets its own registry.

## `camus_registry.csv` — CAMUS's own CSV, enriched + concatenated

CAMUS already writes its family as a CSV. Per `-o <prefix>` it emits
`<prefix>.csv` with **one row per k** and three columns:

| CAMUS column | meaning |
|---|---|
| `Number of Branches` | k = added reticulation edges (row k=0 is the guide tree itself) |
| `Quartet Satisfied Percent` | CAMUS's own fit score for that network |
| `Extended Newick` | the network (extended newick, inline) |

Don't reinvent this. The writer **reads each run's `<name>.csv`, prepends our
identity columns, and appends the rows** to a per-shard file; compact
concatenates shards → `camus_registry.csv` (reuse
`scripts/lib/inference/registry.py` shard/compact machinery). One row per
(dataset, guide_tree, k).

Columns = ours + CAMUS's (renamed to snake_case):

- `dataset_id` — canonical input CSV path (join key, same as tree registry).
- `guide_tree` — which guide produced it (`mp|ga|astral3|true_tree`).
- `config_hash`, `runtime_seconds`, `status`, `ran_at`, `log_path` — run metadata
  as in the tree registry (runtime is whole-family; see open questions).
- `k` ← `Number of Branches`.
- `qsat_percent` ← `Quartet Satisfied Percent`.
- `network_newick` ← `Extended Newick` (inline, like the tree registry's
  `point_estimate_newick`).

No sim metadata is denormalized in — matching `scores.csv`, which stores only its
own fields and recovers everything else (incl. the true `horizontal_edges`) by
joining `dataset_id → simulated_data_registry.path`. The elbow plot does the same
join for the true edge count.

## Why this shape

Target plot: **x = inferred edges (k), y = FN error**, per condition, to find the
"average elbow" — the k past which adding edges stops cutting error. That needs
every (k, network) addressable with its FN score (from `scoring.md`); the true
edge count comes from the sim-registry join. One row per k gives exactly that; a
single point estimate would throw away the sweep.

## CLI changes

Reuse the existing `pch experiment` surface; the split is by output registry, not
new inference commands.

- `pch experiment inference <yaml>` — **unchanged invocation.** CAMUS is already
  a wired method, so enabling `camus:` runs it here (scheduling/deps reuse). What
  changes internally: `api.infer` returns one `InferenceResult` (one point
  estimate) — that can't hold a network family. CAMUS routes its output to a
  camus-specific writer that enriches CAMUS's CSV and appends to `camus_registry.csv`
  instead of `inference_registry.csv`. Tree methods keep writing the tree
  registry. Same shard/compact model.
- `pch experiment score <yaml>` — stays tree RF (`scores.csv`), untouched.
- `pch experiment network-score <yaml>` — **new.** PhyloNet-based per-k network
  scoring → `network_scores.csv` (see `scoring.md`). Separate command because RF
  and network likelihood are different metrics on different registries.
- `pch experiment status` — may grow a network-row count; optional, not required
  for the elbow.

Atomic `pch infer --method camus ...` stays tree-shaped (one estimate) and is
**not** the network entry point — use the experiment path for the family. Revisit
only if a one-off network run is ever needed.

## Open questions

- Runtime: one CAMUS invocation emits all k at once, so `runtime_seconds` is the
  whole-family time — repeat it on each row (simpler joins), noting it's not per-k.
