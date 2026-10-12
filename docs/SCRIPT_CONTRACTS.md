# Script Contracts

I/O contracts for the primitives the inference API shells out to (M0 of the CLI migration). The API depends on exactly these — change a script, update the row.

Scratch dir for all `run*.sh`: **`$PCH_SCRATCH`** (default `$HOME/scratch`), `mkdir -p`'d on entry. Override per-run to isolate temp files.

| Primitive | Invocation | Inputs | stdout | Outputs (files) | Exit |
|-----------|-----------|--------|--------|-----------------|------|
| **quartet gen** | `python3 -m scripts.py.printQuartets -i <csv> [-w]` | dataset CSV; `-w` = wASTRAL weighted format | the quartets (ASTRAL3 format; wASTRAL unique-quartets to stdout + weights to stderr) | — (caller redirects) | non-zero on bad CSV |
| **MP4** | `bash scripts/sh/runMP4.sh --runid R --input <csv> --name N --output <dir>` | dataset CSV, name, output dir | progress (✅ lines) | `<dir>/MP4/trees/N-maj.tree` (point estimate, Newick), `<dir>/MP4/trees/N.trees` (parsimony set, NEXUS), `<dir>/MP4/scores/N.scores`, `<dir>/MP4/logs/` | non-zero on PAUP failure |
| **GA** | `bash scripts/sh/runGA.sh --runid R --input <csv> --name N --output <dir>` | dataset CSV, name, output dir; `MB_EXEC` set | progress | `<dir>/GA/trees1/N.trees` (posterior, NEXUS), `<dir>/GA/trees/N.tree` (MCC point estimate, Newick) | non-zero on MrBayes failure |
| **ASTRAL** | `bash scripts/sh/runASTRAL3.sh -H R -i <csv> -o <dir> -V "PCH_W_ASTRAL3" -n N [-S mp4,ga] [-x]` | dataset CSV; `-S` sources need their MP4/GA outputs under `<dir>` (default `none`: quartets only) | progress | `<dir>/PCH_W_ASTRAL3/trees/N.tree` (Newick), `<dir>/PCH_W_ASTRAL3/logs/N.log` | non-zero on ASTRAL failure |
| **guide tree** | `python3 -m scripts.py.guide_tree --guide G --input <csv> --output <dir> --outgroup L` | `G` from `GUIDE_TREES` (`scripts/lib/model/guide_tree.py`), e.g. `pch_astral3`, `true_tree`; any dataset CSV for a method guide, which needs that method's point estimate under `<dir>`; `true_tree` needs a dataset inside an experiment's `simulation_data`; outgroup label `L` | one Newick tree: binary topology (polytomies resolved, seeded), rooted on `L` | — (caller redirects) | non-zero if `true_tree`'s dataset is outside an experiment, the estimate is missing, or `L` is not in the tree |
| **CAMUS** | `bash scripts/sh/runCAMUS.sh --runid R --input <csv> --name N --output <dir> --guide-tree G --outgroup L` | dataset CSV; one guide tree; `PCH_CAMUS_PROCS` (default 1) | progress, then CAMUS's CSV | `<dir>/CAMUS/networks/N.csv` (CAMUS's raw CSV), `N.log`, `N.png`; `CamusRunner.execute` then writes `N.family.csv` | non-zero on a guide tree that is not rooted and binary, or on CAMUS failure |
| **SNaQ** | `bash scripts/sh/runSNAQ.sh --runid R --input <csv> --name N --output <dir> --guide-tree G [--procs P]` | simulated dataset CSV (hmax and outgroup from its registries); start tree `G` (as **guide tree**); `P` Julia workers (default 1; config `snaq.procs`) | progress, then SNaQ's | `<dir>/SNAQ/networks/N.net` (point estimate: lowest `-loglik` network consistent with the outgroup, rerooted on it, Rich newick; absent if none), `N.choice` (its 0-based `.networks` row, or `none`), SNaQ's `N.{out,log,networks}`; `SnaqRunner.execute` then writes `N.family.csv` | non-zero outside an experiment, without an outgroup, on SNaQ failure, or after 12 h (10 runs; hours at 31 leaves) |
| **model graph** | `python3 -m scripts.py.model_graph --input <csv>` | simulated dataset CSV | `<horizontal_edges> <outgroup_label\|none>` | — | non-zero outside an experiment |
| **TOB-QMC** | `bash scripts/sh/runTOBQMC.sh --runid R --input <csv> --name N --output <dir>` | dataset CSV; `bin/tree-qmc` built with R | progress, then TREE-QMC's log | `<dir>/TOB_QMC/trees/N.tree` (tree of blobs, Newick) | non-zero if TREE-QMC lacks TOB support |
| **NetCS** | `bash scripts/sh/runNETCS.sh --runid R --input <csv> --name N --output <dir>` | simulated dataset CSV (outgroup from its registries); `<dir>/TOB_QMC/trees/N.tree` rooted on the outgroup; `bin/tree-qmc` | progress, then TREE-QMC's log | `<dir>/NETCS/networks/N.raw.net` (one eNewick line, as NetCS wrote it; stale `N.{net,raw.net,family.csv}` are removed first); `NetcsRunner.execute` then writes `N.family.csv` and, if the output is rooted on the outgroup, `N.net` (copy of `N.raw.net`) | non-zero outside an experiment, without an outgroup, on a tree of blobs that is missing or not rooted on the outgroup, or on NetCS failure; 0 when NetCS reroots |
| **RFScorer** | `Rscript scripts/R/RFScorer.R -i <trees> -f newick\|nexus -r <ref_newick> -m <1-4> -p 0\|1 [-x leaf]` | estimate tree(s), reference Newick (binary, unrooted) | **exactly one line `fn_rate fp_rate`** (space-separated floats); all progress → stderr | — | non-zero on bad input / assertion |
| **consensus** | `Rscript scripts/R/consensusTree.R -i <trees> -m <1-4> -p 0\|1 -o <out> [-d N]` | tree set (NEXUS), `-m` resolve mode, `-d` burn-in % | progress → stderr | one Newick tree to `-o` | non-zero on unreadable input |

`-m` resolve modes (RFScorer / consensus): `1`=average, `2`=majority consensus, `3`=MAP, `4`=MCC.

Legacy `scripts/sh/runASTRAL.sh` (folder `ASTRAL(Q,B)`) is kept unchanged for the old bash pipeline; the CLI shells out to `runASTRAL3.sh`, which follows the `PCH_<METHOD>(<params>)` folder convention.

## M0 decisions per primitive (keep `.sh` wrapper vs. inline in Python)

For M1, the Python API (`runners.py` / `api.infer`) targets these wrappers as v1. Where a wrapper only sequences steps, M1 may inline the orchestration and shell out only to the binary/R — recorded here as that work happens:

- **MP4 / GA / ASTRAL** — keep the `.sh` wrappers for now (they bundle real multi-step glue: R nexus-gen → binary → R consensus). Revisit if the glue gets thin.
- **RFScorer / consensus** — called directly via `Rscript` from the API (single R invocation, no wrapper needed).
- **runASTRAL3.sh** — thin-glue inlining candidate (two Python steps + one java); can now fold into `ASTRAL3Runner.execute`. Deferred past M3.
