# BROOQS network inference — implementation plan (#57)

Terms (tree of blobs, k, network family, outgroup, contact edge): `CONTEXT.md`.
Sibling plan: `spec/netcs/PLAN.md`. Shared prerequisites (PR A, PR B) and the shared
data-model breaks are written here once.

## Goal

**Run BROOQS end to end and put raw scores on disk.** BROOQS (paper v2,
[bioRxiv 2026.08.31.748319](https://www.biorxiv.org/content/10.64898/2026.08.31.748319v2))
expands a tree of blobs into a level-1 network: one cycle and one hybrid per blob.
`tob_qmc` supplies the tree of blobs.

**Done when:** `experiments/brooqs_smoke` (30 taxa + `OUT`, h = 1, 2) runs simulation →
inference → network-score on the cluster and writes `network_scores.csv` rows for `brooqs`.
No figures, no sweeps, no tuning of TOB-QMC's alpha.

## What BROOQS does

Verified by building and running commit `17b25b2` on macOS arm64, unless marked.

| | Fact |
|---|---|
| Command | `python3 count_quartets.py -i <gene_trees> -t <tree_of_blobs> -o <out> [--rooted]` (entry point `brooqs = count_quartets:main`) |
| `-i` | One Newick per line, first token only. PCH-W quartet lines `((a,b),(c,d));` work unchanged. A leaf absent from `-t` raises `KeyError`, exit 1. |
| `-t` | First line, plain Newick; lengths and support unused. Every non-root node with ≥ 3 children, and a root with ≥ 4, is a blob. |
| `-o` | One eNewick line: topology only, no γ, no score. Hybrids `#H0, #H1, …`, one per blob. Stdout carries debug matrices, so read `-o`, never stdout. |
| No blobs | Echoes the tree, exit 0 (k = 0). |
| Reticulation count | = number of blobs. No flag. |
| Rooting, default | May reroot at an arbitrary leaf (`t26`, `t4` in trials). |
| Rooting, `--rooted` | Never reroots; if the best hybrid is the group containing the root, takes the next-best. |
| Determinism | Identical across runs and seeds at these flags. Single-threaded. |
| Quartet multiplicity | Changes the network: weight-repeated ≠ unique. |
| Cost, 30 taxa | 43 s, 259 MB on 131,564 weight-repeated quartets. |
| Broken on quartets | `--filter` crashes (`LinAlgError`). `--dist-var` runs but needs branch lengths we lack. |
| 4-blobs | Paper §2.2.2: the hybrid of a 4-cycle "is not theoretically identifiable from quartet CFs". |

On our data (4 simulated datasets with `OUT`, trees of blobs rooted on `OUT`, `--rooted`):
output rooted on `OUT` in 8 of 8 runs; hybrids = polytomy count in 4 of 4 (alpha 0.25);
33–78 s with blobs, 2 s without.

Unverified: Linux run; the paper's flags (it names none; it roots the tree of blobs on the
outgroup, §2.3.3).

Rooting changes the score (investigator's subagent, alpha-0.25 tree, `t1` as outgroup):

| Mode | FN | FP |
|---|---|---|
| default | 0.314 | 0.250 |
| `--rooted`, tree as TOB-QMC wrote it | 0.343 | 0.281 |
| `--rooted`, tree rooted on the outgroup | 0.257 | 0.188 |

## Settled decisions

| Decision | Rationale |
|---|---|
| Tree of blobs = fixed dependency on `tob_qmc`: `get_dependencies()` returns it; no config field | One source exists. Not a guide tree, not `GuidedNetworkConfig`. |
| `tob_qmc` stays a `TreeInferenceMethod` | A third category touches scheduler, scoring, status. Recorded as a break. |
| Tree of blobs is rooted on the outgroup by `tob_qmc` itself (PR B); BROOQS runs `--rooted` | Paper roots on the outgroup; best of the three modes above; one tree on disk for both methods. |
| Outgroup comes from the dataset's model graph (`scripts.py.model_graph`), as SNaQ | One source of truth; never hardcode `OUT`. No outgroup → BROOQS fails with SNaQ's message. |
| Quartets: PCH-W, once per unit of weight, regenerated per run | Same data as the tree of blobs; every method gets weighted quartets. |
| `BrooqsConfig` has no fields; BROOQS defaults plus `--rooted` | As `TobQmcConfig`. Add a field when a sweep needs one. |
| k = 0 is an `ok` row, scored | It is the method's answer. Expected often: see break 8. |
| `#H0` → `#H1` at scoring, not in the registry (PR A) | The newick stays "as the tool wrote it". |
| Install: a uv git dependency at `17b25b2` (`pyproject.toml`, `uv.lock`); `make setup` installs it | Upstream ships a `pyproject.toml`; one venv, no clone in `bin/`. |
| Smoke on the cluster only | `tob_qmc` cannot run on the Mac (break 11). |

## I/O in our pipeline

```text
dataset.csv
 ├─ scripts.py.model_graph            → outgroup label (none → exit 1)
 ├─ scripts.py.printQuartets          → $PCH_SCRATCH/tmp_quartet_<runid>.txt
 ├─ <cond>/TOB_QMC/trees/<stem>.tree  (dependency, rooted on the outgroup; missing → exit 1)
 └─ brooqs -i <quartets> -t <tob> -o <net> --rooted
      → <cond>/BROOQS/networks/<name>.net          point estimate, as BROOQS wrote it
      → <cond>/BROOQS/logs/<name>.log
```

No family CSV: `network-score` scores the point estimate, `edges_added` = distinct `#H<n>`
labels. `is_point_estimate_optional` stays False: BROOQS always writes a network.

## PRs

Independent, each off `main`. C scores correctly only after A and runs only after B.

### PR A — `score_network` accepts 0-indexed hybrids

Merged: #61.

- `scripts/lib/inference/scoring.py`: if the estimate has `#H0`, shift every `#H<n>` up by
  one before CmpNets. Beside the existing annotation strip.
- Test: a `#H0, #H1` network scores as its `#H1, #H2` twin.
- `docs/SCHEMAS.md` (network family, `network_newick` row): scoring also renumbers hybrids.

### PR B — `tob_qmc` roots the tree of blobs on the outgroup

Merged: #63.

- `scripts/sh/runTOBQMC.sh`: read the outgroup with `scripts.py.model_graph`; pass
  `--root <outgroup>` to `tree-qmc --blob` when there is one; unrooted as today when `none`.
- `docs/method_docs/tob_qmc/README.md`, `docs/SCRIPT_CONTRACTS.md`: output is rooted on the
  outgroup. `docs/MIGRATIONS.md`: `tob_qmc` rows from before this PR hold unrooted trees and
  the same `config_hash`; delete them to rerun.
- Rooting while building is deliberate, and not neutral: TREE-QMC's per-edge search depends
  on the root. Same quartets, alpha 0.25: 23 splits rooted, 24 unrooted (each repeatable);
  identical at the default alpha. `--rootonly` afterwards is no alternative: it resolves
  polytomies.
- Cluster check: output starts `(<outgroup>,(`.

### PR C — BROOQS

| File | Change |
|---|---|
| `pyproject.toml`, `uv.lock` | `brooqs` git dependency pinned at `17b25b2`; `uv sync` installs the `brooqs` command. |
| `scripts/lib/model/methods.py` | `NetworkInferenceMethod.BROOQS = "brooqs"` |
| `scripts/lib/experiment.py` | `BrooqsConfig(RunnableConfig)`, one runner; `MethodConfig.brooqs`; `get_enabled_configs` |
| `scripts/lib/inference/method_config.py`, `runners/__init__.py` | Registry entries, after `TOB_QMC` |
| `scripts/lib/inference/runners/brooqs.py` | `BrooqsRunner`: `get_dependencies() -> [TOB_QMC]`; `build_argv` as `TobQmcRunner`; no family; paths under `BROOQS/{networks,logs}` |
| `scripts/sh/runBROOQS.sh` | Arguments as `runTOBQMC.sh`; steps as the diagram above |
| `experiments/brooqs_smoke/` | `tob_qmc_smoke` plus `outgroup_label: OUT`, `tob_qmc: {}`, `brooqs: {}` |
| `tests/scripts/lib/inference/test_brooqs_runner.py` | After `test_tob_qmc_runner.py`: one runner from `{}`, dependency, argv, `api.infer` with a stubbed command, no group estimate |
| `scripts/py/cli/handle_network_score.py` | A run with no family is scored on its point estimate; `edges_added` counted from hybrids |
| Docs | `docs/method_docs/brooqs/README.md` from `TEMPLATE.md`; rows in `SCRIPT_CONTRACTS.md`, `ARCHITECTURE.md`, `KEYS.md`, `SCHEMAS.md`, `CLI.md` |

SLURM tier: light.

Smoke checks, in order:
1. Every `.net` has the outgroup as a child of the root.
2. `edges_added` equals the polytomy count of the matching tree of blobs.
3. `network_scores.csv` has an `ok` row per dataset, `guide_tree` null.
4. Record how many datasets gave k = 0.

## Where the data model breaks

1. **"Guide tree" does not cover a tree of blobs.** It is unrooted in nature and has
   polytomies. BROOQS and NetCS are network methods outside `GuidedNetworkConfig`;
   `network_scores.guide_tree` is null for them.
2. **`tob_qmc` is a tree method that is not a species tree.** It sits in `GUIDE_TREES`, so
   each guided method excludes it by hand (`SNAQ_GUIDE_TREES`, `CAMUS_GUIDE_TREES`), and
   `experiment score` RF-scores it against the base tree, which penalises correct blobs.
   No reference tree of blobs exists, as oracle input or as scoring target.
3. **Network family assumes a guide tree** ("one per k, starting at k = 0 (the guide
   tree)"). Here a run gives one network and k is fixed by the tree of blobs.
4. **`network_newick` "as the tool wrote it" is not scoreable as written**: CmpNets rejects
   `#H0`. The normalisation lives at scoring (PR A).
5. **A dependency names a method, not a config or an output version.** The BROOQS
   `config_hash` covers neither TOB-QMC's settings nor PR B's rooting change. Stale unrooted
   trees keep their registry rows and nothing checks them; `docs/MIGRATIONS.md` says to drop them.
6. **Two outgroup sources.** `CamusConfig.outgroup_label` duplicates
   `simulation.outgroup_label`; SNaQ, `tob_qmc`, BROOQS and NetCS read the model graph.
   Follow-up PR: CAMUS reads it too. Real (non-simulated) datasets have no model graph, so
   no outgroup source at all.
7. **The reference is not level-1 and not single-direction.** Each contact event is two
   contact edges (ADR 0001); BROOQS gives one hybrid per blob, so FN > 0 whenever h ≥ 1.
8. **PCH-W weights are read as gene-tree counts**, and at TOB-QMC's defaults (alpha 1e-7,
   the paper's value) our data showed no blobs: two 30-taxon network datasets gave binary
   trees (min tree-test p 0.08 at 80 characters, 0.002 at 640), as did all four `OUT`
   datasets. At alpha 0.25 those four each gave two blobs, degrees 4–10. Later, through
   the pipeline at defaults, 2 of 2 freshly simulated datasets each gave one degree-4
   polytomy and k = 1. So at defaults k = 0 rows (a tree scored as a network) occur, as do
   small blobs.
9. **`is_best` means "the method's own pick by its objective"**; these tools have no
   objective value and one candidate.
10. **Resume keeps the first success**, which hides run-to-run differences in tools without
    a seed (NetCS, see its plan).
11. **The Mac cannot run `tob_qmc`.** `bin/tree-qmc` resolves to the `bin/TREE-QMC/`
    directory on a case-insensitive filesystem, and `53b15e5` needs patches for Apple clang.
    Separate issue.

## Follow-ups, not in these PRs

- CAMUS takes the outgroup from the model graph (break 6).
- `bin/tree-qmc` collision and macOS build (break 11).
- `alpha`/`beta` on `TobQmcConfig`, once someone studies blob yield (break 8).
- A reference tree of blobs for scoring `tob_qmc` (break 2).
