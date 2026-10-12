# NetCS network inference — implementation plan (#58)

Terms (tree of blobs, k, network family, outgroup): `CONTEXT.md`.
Sibling plan: `spec/brooqs/PLAN.md`; it holds the shared prerequisites (PR A: hybrid
renumbering at scoring; PR B: `tob_qmc` roots on the outgroup) and the shared data-model
breaks. Only what differs is here.

## Goal

**Run NetCS end to end and put raw scores on disk.** NetCS
([bioRxiv 2026.06.06.730607](https://www.biorxiv.org/content/10.64898/2026.06.06.730607v2))
resolves each blob of degree ≥ 5 in a tree of blobs into a cycle with one hybrid.
`tob_qmc` supplies the tree of blobs.

**Done when:** `experiments/netcs_smoke` (30 taxa + `OUT`, h = 1, 2) runs simulation →
inference → network-score on the cluster and writes `network_scores.csv` rows for `netcs`.

## What NetCS does

Verified by running TREE-QMC `53b15e5` (our pin; a patched macOS build), unless marked.
Paper body unread (abstract only).

| | Fact |
|---|---|
| Where | A mode of `bin/tree-qmc`; in our pin since `bafc6a6`. No install change. Absent from `-h`. |
| Command | `tree-qmc --network -i <gene_trees> --at <tree_of_blobs> -o <out> --override` |
| `-i` | Gene-tree Newick, one per line. PCH-W quartet lines work unchanged. `--quartets` wants a qCF CSV and aborts on plain quartets; do not use it. |
| `--at` | First line, plain Newick with polytomies. `TOB_QMC/trees/<stem>.tree` works unchanged. NetCS does not build the tree of blobs itself. |
| `-o` | One eNewick line: topology only, no γ, no score. Hybrids `#H0, #H1, …`. Without `-o`, or without `--override` on an existing file, the network goes to stdout with the log. |
| Blobs resolved | Degree ≥ 5 only. Smaller blobs stay polytomies in the output ("unable to identify the hybridization"). |
| Reticulation count | = blobs of degree ≥ 5. No flag. |
| Other flags read | `--alpha` 1e-7, `--beta` 0.95, `--iter_limit_blob` 2n². Left at defaults. |
| Cost, 30 taxa | 1–3 s on a binary tree of blobs, 3–27 s with blobs (12 `api.infer` runs); 0.8 GB on 131,564 quartets (TOB-QMC on the same data: 82 s). |

### Rooting

Checked on upstream's `tutorial/NetCS` data.

| `--at` tree rooted on | Log | Output |
|---|---|---|
| a taxon not below a hybrid (`l20`, `t9`) | "rooting is valid" | Rooted on that taxon. Identical in 4 of 4 runs. |
| a taxon below a hybrid (`l34`, `l49`) | "not valid … Perform rerooting on the edge above taxon X" | Rooted elsewhere; 3 different files in 4 runs; unary nodes left behind. Exit 0. |
| any, plus `--root <taxon>` | "Rooting species tree at …" | Segfault, exit 139, no file. |

So NetCS keeps a valid input root. With PR B the tree of blobs arrives rooted on the
outgroup, and the output is rooted on it unless NetCS puts the outgroup below a hybrid.
No Julia step. Upstream issue draft: `spec/netcs/upstream-root-issue.md`.

On our data (simulated datasets with `OUT`, trees of blobs rooted on `OUT`):

- Default alpha, 4 fixture datasets: every tree of blobs is binary; NetCS echoes it, rooted
  on `OUT`, k = 0.
- Default alpha, 2 new datasets through the real pipeline: each tree of blobs has one
  degree-4 polytomy; NetCS keeps it, k = 0, rooted on `OUT`, `is_best` true, scored
  (FN 0.419 / FP 0.357; FN 0.422 / FP 0.071).
- Alpha 0.25 (blobs of degree 4–10): 2 of 4 first runs put `OUT` below a hybrid and
  rerooted elsewhere, leaving a unary `(OUT)` node.
- **The verdict varies per run, but mostly per dataset.** NetCS's choice of hybrid varies,
  and with it whether the input root is valid. Alpha 0.25, repeat `api.infer` runs:
  `sim_1_1_1` rooted on `OUT` 35 times, rerooted once; `sim_2_1_1` rooted 0 of 32
  (6 distinct outputs in 30). Two new datasets through the real pipeline (k = 1, k = 2, as
  expected): rerooted in 10 of 10 runs, 9 distinct roots, so no network with a hybrid was
  scored there.
- Scored once renumbered: rooted on `OUT` FN 0.32 / FP 0.32; not rooted FN 0.67 / FP 0.58.

## Settled decisions

Shared ones (fixed `tob_qmc` dependency, outgroup from the model graph, weight-repeated
PCH-W quartets, no config fields, k = 0 is `ok`, `#H0` renumbered at scoring, cluster-only
smoke) are in the BROOQS plan. NetCS-specific:

| Decision | Rationale |
|---|---|
| Point estimate only when the output is rooted on the outgroup; else none, and the family row has `is_best` false | SNaQ's rule for a network inconsistent with the outgroup. Cluster scoring is root-dependent; an arbitrary root would score noise. |
| The check is ours, in Python, on the output Newick | NetCS exits 0 either way. No reroot code: NetCS did the rooting or nobody does. |
| Unresolved 4-blobs are recorded as written | They show up as FN. |
| Accept non-determinism; state it in the method doc | No seed flag. Repeat-and-vote is analysis. |
| No dependency on the SNaQ/Julia install | Rerooting with `rootatnode!` is not needed. |

## I/O in our pipeline

```text
dataset.csv
 ├─ scripts.py.model_graph            → outgroup label (none → exit 1)
 ├─ scripts.py.printQuartets          → $PCH_SCRATCH/tmp_quartet_<runid>.txt
 ├─ <cond>/TOB_QMC/trees/<stem>.tree  (dependency; must be rooted on the outgroup, else exit 1)
 └─ bin/tree-qmc --network -i <quartets> --at <tob> -o <raw> --override
      → <cond>/NETCS/networks/<name>.raw.net      as NetCS wrote it
      → <cond>/NETCS/networks/<name>.family.csv   NetcsRunner.execute; one row
      → <cond>/NETCS/networks/<name>.net          copy of raw, only if rooted on the outgroup
      → <cond>/NETCS/logs/<name>.log
```

Family row: `edges_added` = distinct `#H<n>` labels, `network_newick` = the raw line,
`is_best` = "the outgroup is a child of the root". `is_point_estimate_optional = True`
(as `SnaqRunner`): the run is `ok` on the family alone. Rows with `is_best` false are not
scored (`handle_network_score.read_families`).

## PR D — NetCS

Off `main`, independent of the BROOQS PR. Scores correctly after PR A; runs after PR B.
Touches the same registry lines as BROOQS; the second to merge rebases.

| File | Change |
|---|---|
| `scripts/lib/model/methods.py` | `NetworkInferenceMethod.NETCS = "netcs"` |
| `scripts/lib/experiment.py` | `NetcsConfig(RunnableConfig)`, one runner; `MethodConfig.netcs`; `get_enabled_configs` |
| `scripts/lib/inference/method_config.py`, `runners/__init__.py` | Registry entries, after `TOB_QMC` |
| `scripts/lib/inference/runners/netcs.py` | `NetcsRunner`: `get_dependencies() -> [TOB_QMC]`; `build_argv` as `TobQmcRunner`; `execute` reads the outgroup (`ModelGraph.from_dataset`), writes the family via `netcs_to_family(raw_path, outgroup_label)` and copies raw → `.net` when rooted; `is_point_estimate_optional = True` |
| `scripts/sh/runNETCS.sh` | Arguments as `runTOBQMC.sh`; steps as the diagram. `rm -f` a stale `.net` first. |
| `scripts/sh/installs/install_w_tree_qmc.sh` | Header comment: the build also provides NetCS |
| `experiments/netcs_smoke/` | `tob_qmc_smoke` plus `outgroup_label: OUT`, `tob_qmc: {}`, `netcs: {}` |
| `tests/scripts/lib/inference/test_netcs_runner.py` | One runner from `{}`, dependency, argv, `api.infer` with a stubbed command; family from: rooted 1-hybrid network (best, `.net` written), network rooted elsewhere (not best, no `.net`, run still `ok`), plain tree (k = 0) |
| Docs | `docs/method_docs/netcs/README.md` from `TEMPLATE.md` (rooting table above, non-determinism, degree ≥ 5); rows in `SCRIPT_CONTRACTS.md`, `ARCHITECTURE.md`, `KEYS.md`, `SCHEMAS.md` (`is_best` for NetCS), `CLI.md` |

SLURM tier: light.

Smoke checks, in order:
1. Count runs where the outgroup is not a child of the root; log line says "not valid".
2. `edges_added` equals the count of degree-≥ 5 blobs in the matching tree of blobs.
3. `network_scores.csv` has an `ok` row for every `is_best` network, `guide_tree` null.
4. Record how many datasets gave k = 0, and how many had only blobs of degree < 5.

If check 4 says every dataset is k = 0: merge anyway (settled), report the counts on #58.

## Where the data model breaks

Breaks 1–11 in `spec/brooqs/PLAN.md` apply. NetCS adds:

12. **A "network" may keep polytomies.** Blobs of degree < 5 are unresolved, so the output
    is neither binary nor a full level-1 network. CmpNets scores it (checked once
    renumbered); nothing in the schema says a row is partly resolved.
13. **No point estimate ≠ failure, and is decided by rooting, not by the method.** The `ok`
    rule passes on the family alone; the row's network is on disk but unscored. Analyses
    must count these rows or they vanish.
14. **Run-to-run differences are invisible** (break 10, concrete here): NetCS's hybrid, its
    root, and so `is_best` vary per run on the same input; resume keeps the first success.
    Whether a dataset has a scored NetCS network is mostly per dataset, sometimes per run.
15. **`tob_qmc`'s root now carries meaning for NetCS** (it decides rooted vs not), yet it is
    not part of any config or hash (break 5).

## Follow-ups, not in this PR

- File `spec/netcs/upstream-root-issue.md` upstream; a working `--root` makes the
  rooted-on-outgroup check and `is_best` false rows unnecessary.
- Read the paper body for its alpha/beta and degree-< 5 treatment; fill the method doc's
  "Versus the paper".
