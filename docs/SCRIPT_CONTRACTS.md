# Script Contracts

I/O contracts for the primitives the inference API shells out to (M0 of the CLI migration). The API depends on exactly these — change a script, update the row.

Scratch dir for all `run*.sh`: **`$PCH_SCRATCH`** (default `$HOME/scratch`), `mkdir -p`'d on entry. Override per-run to isolate temp files.

| Primitive | Invocation | Inputs | stdout | Outputs (files) | Exit |
|-----------|-----------|--------|--------|-----------------|------|
| **quartet gen** | `python3 -m scripts.py.printQuartets -i <csv> [-w]` | dataset CSV; `-w` = wASTRAL weighted format | the quartets (ASTRAL3 format; wASTRAL unique-quartets to stdout + weights to stderr) | — (caller redirects) | non-zero on bad CSV |
| **MP4** | `bash scripts/sh/runMP4.sh --runid R --input <csv> --name N --output <dir>` | dataset CSV, name, output dir | progress (✅ lines) | `<dir>/MP4/trees/N-maj.tree` (point estimate, Newick), `<dir>/MP4/trees/N.trees` (parsimony set, NEXUS), `<dir>/MP4/scores/N.scores`, `<dir>/MP4/logs/` | non-zero on PAUP failure |
| **GA** | `bash scripts/sh/runGA.sh --runid R --input <csv> --name N --output <dir>` | dataset CSV, name, output dir; `MB_EXEC` set | progress | `<dir>/GA/trees1/N.trees` (posterior, NEXUS), `<dir>/GA/trees/N.tree` (MCC point estimate, Newick) | non-zero on MrBayes failure |
| **ASTRAL** | `bash scripts/sh/runASTRAL3.sh -H R -i <csv> -o <dir> -V "PCH_ASTRAL_3(11,5)" -n N [-x]` | dataset CSV; requires MP4/GA outputs under `<dir>` for bipartitions (non-exact) | progress | `<dir>/PCH_ASTRAL_3(Q,B)/trees/N.tree` (Newick), `<dir>/PCH_ASTRAL_3(Q,B)/logs/N.log` | non-zero on ASTRAL failure |
| **RFScorer** | `Rscript scripts/R/RFScorer.R -i <trees> -f newick\|nexus -r <ref_newick> -m <1-4> -p 0\|1 [-x leaf]` | estimate tree(s), reference Newick (binary, unrooted) | **exactly one line `fn_rate fp_rate`** (space-separated floats); all progress → stderr | — | non-zero on bad input / assertion |
| **consensus** | `Rscript scripts/R/consensusTree.R -i <trees> -m <1-4> -p 0\|1 -o <out> [-d N]` | tree set (NEXUS), `-m` resolve mode, `-d` burn-in % | progress → stderr | one Newick tree to `-o` | non-zero on unreadable input |

`-m` resolve modes (RFScorer / consensus): `1`=average, `2`=majority consensus, `3`=MAP, `4`=MCC.

Legacy `scripts/sh/runASTRAL.sh` (folder `ASTRAL(Q,B)`) is kept unchanged for the old bash pipeline; the CLI shells out to `runASTRAL3.sh`, which follows the `PCH_<METHOD>(<params>)` folder convention.

## M0 decisions per primitive (keep `.sh` wrapper vs. inline in Python)

For M1, the Python API (`runners.py` / `api.infer`) targets these wrappers as v1. Where a wrapper only sequences steps, M1 may inline the orchestration and shell out only to the binary/R — recorded here as that work happens:

- **MP4 / GA / ASTRAL** — keep the `.sh` wrappers for now (they bundle real multi-step glue: R nexus-gen → binary → R consensus). Revisit if the glue gets thin.
- **RFScorer / consensus** — called directly via `Rscript` from the API (single R invocation, no wrapper needed).
- **runASTRAL3.sh** — thin-glue inlining candidate (two Python steps + one java); fold into `ASTRAL3Runner` when the runner protocol grows a `run()` beyond `build_argv`. Deferred past M3.
