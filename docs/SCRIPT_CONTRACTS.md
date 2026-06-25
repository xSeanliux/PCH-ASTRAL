# Script Contracts

I/O contracts for the primitives the inference API shells out to (M0 of the CLI migration). The API depends on exactly these — change a script, update the row.

Scratch dir for all `run*.sh`: **`$PCH_SCRATCH`** (default `$HOME/scratch`), `mkdir -p`'d on entry. Override per-run to isolate temp files.

| Primitive | Invocation | Inputs | stdout | Outputs (files) | Exit |
|-----------|-----------|--------|--------|-----------------|------|
| **quartet gen** | `python3 -m scripts.py.printQuartets -i <csv> [-w]` | dataset CSV; `-w` = wASTRAL weighted format | the quartets (ASTRAL3 format; wASTRAL unique-quartets to stdout + weights to stderr) | — (caller redirects) | non-zero on bad CSV |
| **MP4** | `bash scripts/sh/runMP4.sh --runid R --input <csv> --name N --output <dir>` | dataset CSV, name, output dir | progress (✅ lines) | `<dir>/MP4/trees/N-maj.tree` (point estimate, Newick), `<dir>/MP4/trees/N.trees` (parsimony set, NEXUS), `<dir>/MP4/scores/N.scores`, `<dir>/MP4/logs/` | non-zero on PAUP failure |
| **GA** | `bash scripts/sh/runGA.sh --runid R --input <csv> --name N --output <dir>` | dataset CSV, name, output dir; `MB_EXEC` set | progress | `<dir>/GA/trees1/N.trees` (posterior, NEXUS), `<dir>/GA/trees/N.tree` (MCC point estimate, Newick) | non-zero on MrBayes failure |
| **ASTRAL** | `bash scripts/sh/runASTRAL.sh -H R -i <csv> -o <dir> -q Q -b B -n N [-x]` | dataset CSV; requires MP4/GA outputs under `<dir>` for bipartitions (non-exact) | progress | `<dir>/ASTRAL(Q,B)/trees/N.tree` (Newick), `<dir>/ASTRAL(Q,B)/logs/N.log` | non-zero on ASTRAL failure |
| **wASTRAL** | `bash scripts/sh/runWASTRAL.sh --runid R --input <csv> --name N --output <dir>` | dataset CSV; quartets via `printQuartets -i <csv> -w` | progress (✅ lines) | `<dir>/WASTRAL/trees/N.tree` (Newick), `<dir>/WASTRAL/trees/N.log` | non-zero on wastral failure |
| **TREE-QMC** | `bash scripts/sh/runTREEQMC.sh --runid R --input <csv> --name N --output <dir> [--norm <0\|1\|2>]` | dataset CSV; quartets via `printQuartets -i <csv> -w`, re-formatted to `((A,B),(C,D));weight`; `--norm` → `--norm_atax` (default 2) | progress (✅ lines) | `<dir>/TREEQMC/trees/N.tree` (Newick), `<dir>/TREEQMC/trees/N.log` | non-zero on tree-qmc failure |
| **RFScorer** | `Rscript scripts/R/RFScorer.R -i <trees> -f newick\|nexus -r <ref_newick> -m <1-4> -p 0\|1 [-x leaf]` | estimate tree(s), reference Newick (binary, unrooted) | **exactly one line `fn_rate fp_rate`** (space-separated floats); all progress → stderr | — | non-zero on bad input / assertion |
| **consensus** | `Rscript scripts/R/consensusTree.R -i <trees> -m <1-4> -p 0\|1 -o <out> [-d N]` | tree set (NEXUS), `-m` resolve mode, `-d` burn-in % | progress → stderr | one Newick tree to `-o` | non-zero on unreadable input |

`-m` resolve modes (RFScorer / consensus): `1`=average, `2`=majority consensus, `3`=MAP, `4`=MCC.

## M0 decisions per primitive (keep `.sh` wrapper vs. inline in Python)

For M1, the Python API (`runners.py` / `api.infer`) targets these wrappers as v1. Where a wrapper only sequences steps, M1 may inline the orchestration and shell out only to the binary/R — recorded here as that work happens:

- **MP4 / GA / ASTRAL** — keep the `.sh` wrappers for now (they bundle real multi-step glue: R nexus-gen → binary → R consensus). Revisit if the glue gets thin.
- **RFScorer / consensus** — called directly via `Rscript` from the API (single R invocation, no wrapper needed).
- **wASTRAL / TREE-QMC** — `.sh` wrappers, BEST-EFFORT. Neither binary runs in dev (wastral built for newer macOS; tree-qmc hits a case-insensitive FS path collision), so these were written without an end-to-end run and tests mock subprocess.

### Needs live verification (binaries don't run in dev)

- **wASTRAL invocation** (`runWASTRAL.sh`): the `bin/wastral -i <quartets> -o <out>` flags are best-effort from ASTER docs. Whether wASTRAL consumes the quartet file directly, needs a weights flag, or wants a different `-i` format is unverified. The weights file (`printQuartets -w` stderr) is currently not passed — confirm how weighted quartets feed wastral on the cluster.
- **TREE-QMC quartet formatting** (`runTREEQMC.sh`): the CLI (`tree-qmc --quartets -i <file> -o <out> --norm_atax <0|1|2>`) is confirmed, but the adaptation from `printQuartets -w` (quartets to stdout, weights to stderr) into tree-qmc's `((A,B),(C,D));weight` line format — trailing-`;` strip + `paste` of weights — is unverified against the binary's parser (delimiter/whitespace tolerance).
