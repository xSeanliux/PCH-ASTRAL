# How to run (legacy bash inference)

This catalogues the legacy bash inference scripts: what each does, its I/O, the key line(s), and caveats. It is the reference for the migration to the config-driven CLI (`scripts/py/cli/main.py`), which does not yet cover inference — these scripts define what inference must reproduce.

The scripts form three groups:

- **Orchestrators** (repo root) — loop over model conditions / datasets and call the runners.
- **Runners** (`scripts/sh/run{ASTRAL,GA,MP4}.sh`) — run one method on one dataset CSV.
- **Scoring/consensus** (`scripts/R/`) — point estimates and FN/FP rates.

Method flags are shared throughout: `a`=ASTRAL III, `A`=ASTRAL IV, `p`=MP4 (parsimony), `g`=GA (Gray & Atkinson). See `REPRODUCIBILITY.md` for the full flag reference.

## Conventions and shared caveats

- **Temp files live in `~/scratch/`** keyed by a random `RUNID` (so parallel runs don't collide). `~/scratch/` must exist. Runners do not clean up their own temp files; the orchestrators `rm` ASTRAL's afterwards.
- **`OS_TYPE='RedHat'`** is hardcoded; the pipeline targets the SLURM/Linux cluster. `mb` is aliased (hence `shopt -s expand_aliases`).
- **Binaries** are git-ignored under `bin/`: `bin/paup` (MP4), `bin/bin/mb` (GA/MrBayes), `ASTRAL/Astral/astral.5.7.8.jar` (ASTRAL III). Install via `scripts/sh/installs/`.
- **Output layout:** `{TREEOUTPUT}/{METHOD}/trees/{name}.tree` (point estimate), `.../trees/{name}.trees` or `trees1/` (the full tree set), `.../logs/`, `.../scores/`. `TREEOUTPUT` is typically `sim_outputs/{MODEL_CONDITION}/`.
- **Migration caveat:** `runASTRAL.sh` calls `printQuartets.py -q $QUARTET`, but the current `printQuartets.py` takes `-i`/`-w` (no `-q`) — the bash layer references a stale CLI. Verify the quartet-generation interface before relying on it.

---

## Orchestrators (repo root)

### `run_inference_sim.sh`
Main driver. Sweeps the hardcoded factor arrays (`E_FACTORS`, `H_FACTORS`, `C_FACTORS`, `SETTINGS` polymorphism levels) × `TREECOUNT` trees × `REPLICA_COUNT` replicates, and for each runs the requested methods, then scores the result against the true tree.
- **Inputs:** flags `-a/-A/-p/-g` (methods), `-q` quartet mode, `-b` bipartition mode, `-f/-h/-C/-s` to restrict to a single factor value. Reads dataset CSVs from `data/simulated_data/{SETTING_NAME}/sim_tree{i}_{r}.csv` and true trees from `data/trees.txt` (line `i`).
- **Outputs:** trees under `sim_outputs/{SETTING_NAME}/{METHOD}/`, plus appended `allscores.txt` (input filename followed by `FN FP` per dataset).
- **Key lines:** dispatch — GA `runGA.sh` (`:98`), MP4 `runMP4.sh` (`:113`), ASTRAL `runASTRAL.sh` (`:129`). Scoring via `RFScorer.R`: GA `:106`, MP4 `:121`, ASTRAL `:140` (and `:142` prunes the extra-root leaf in ASTRAL IV `q=4` mode).
- **Caveat:** **adding a model condition means editing the factor arrays at the top** (`:16-19`). Re-runnable: skips a dataset if its output tree already exists (`:97`, `:112`, `:128`).

### `run_parallel_sim.sh`
SLURM submitter. Generates one `.sbatch` per factor combination that calls `run_inference_sim.sh`, and chains `TIMES` repeated submissions with `--dependency=afterany` (continues where a timed-out job left off).
- **Inputs:** its own hardcoded `METHODS`/`QUARTETS`/`SETTINGS`/factor arrays (`:2-12`). No CLI args.
- **Outputs:** sbatch scripts in `~/scratch/`, SLURM logs in `SLURM_OUT/`.
- **Key lines:** sbatch heredoc + `run_inference_sim.sh` invocation (`:38`); first submit `:39`, dependent re-submits `:43`.
- **Caveat:** cluster-specific (`partition=secondary`, `mem=512000`, conda env `phylo`). Edit arrays to change the sweep.

### `run_specific_dataset.sh`
Single-dataset convenience wrapper: runs chosen methods on one input CSV, no looping, no scoring.
- **Inputs:** `-i` input CSV, `-o` output dir, `-n` name, method flags `-a/-p/-g`, `-q/-b`, `-x` (ASTRAL exact mode).
- **Outputs:** trees under `{output}/{METHOD}/`. Does **not** score.
- **Key lines:** GA `:45`, MP4 `:52`, ASTRAL `:59`.

---

## Runners (`scripts/sh/`)

### `runASTRAL.sh` — ASTRAL III (heuristic / exact)
1. **Generate quartets** from the CSV: `printQuartets.py` (`:53`) → `~/scratch/tmp_quartet_{RUNID}.txt`.
2. **Build the bipartition constraint set** from MP4+GA results: `getResultBipartitions.py -m -g` (`:68`) → `tmp_bipartitions_{RUNID}.bootstrap.trees`. Skipped in exact mode (`-x`, `:63`), which passes no bipartitions.
3. **Run ASTRAL** (`:80`): `java -jar -Xmx512g .../astral.5.7.8.jar` with `-i` quartets, `-f` bipartitions, `-t 1`.
- **Inputs:** `-H` runid, `-i` CSV, `-o` output, `-n` name, `-q` quartet mode, `-b` bipartition mode, `-x` exact.
- **Output:** `{output}/ASTRAL({q},{b})/trees/{name}.tree`; log under `logs/`.
- **Caveats:** **requires MP4 and GA to have run first** (non-exact mode reads their bipartitions). `-Xmx512g` is cluster-sized. Jar path relies on the macOS case-insensitive FS quirk (`ASTRAL/` submodule vs `Astral/` dir — see CLAUDE.md).

### `runMP4.sh` — Maximum Parsimony (PAUP*)
1. **Generate NEXUS** with parsimony settings: `commandLineNex.R -p 3 -m 1.0` (`:46`, `-p 3` = polymorphism resolution mode, `-m` = morph weight).
2. **Run PAUP\*** (`:53`) → moves `paup_out_{RUNID}.trees`/`.scores` into `MP4/trees|scores/{name}` (`:54-55`).
3. **Point estimate = majority consensus**: `consensusTree.R -m 2` (`:58`) → `{name}-maj.tree`.
- **Inputs:** `-H` runid, `-i` CSV, `-n` name, `-o` output. **Output:** the equally-parsimonious tree set `{name}.trees` and the consensus `{name}-maj.tree`.
- **Caveat:** `chmod a+x bin/paup` each run; temp `.nex`/PAUP outputs keyed by RUNID to survive parallelism.

### `runGA.sh` — Gray & Atkinson (MrBayes)
1. **Generate NEXUS** for Bayesian run: `commandLineNex.R --resolve-poly 4 --morph-weight 1.0` (`:53`).
2. **MCMC sampling**: `$MB_EXEC` MrBayes (`:55`) → `Bayes_out_{RUNID}.t`, moved to `GA/trees1/{name}.trees` (`:60`).
3. **Point estimate = MCC tree, burn-in 50%**: `consensusTree.R -m 4 --discard 50` (`:63`) → `GA/trees/{name}.tree`.
- **Inputs:** `-H` runid, `-i` CSV, `-n` name, `-o` output. **Output:** posterior sample `trees1/{name}.trees`, MCC point estimate `trees/{name}.tree`.
- **Caveat:** **set `MB_EXEC` at `:4`** (defaults to `bin/bin/mb`). Cleans up `Bayes_out_*` after (`:70`).

---

## Scoring & consensus (`scripts/R/`)

### `RFScorer.R` — FN/FP rate against the true tree
Computes the **false-negative / false-positive rate** = (missing / extra bipartitions) / (N−3), the normalized Robinson–Foulds halves. Prints `FN FP` to stdout.
- **Key line:** `computeFnFpRate` (`:59`); split comparison is encoding-agnostic via XOR (`:74`). FN/FP normalization at `:94`.
- **Inputs:** `-i` trees, `-f nexus|newick`, `-r` reference newick, `-m` multi-tree resolution, `-x` leaf to prune. If multiple input trees, collapses them first via `-m` (`1`=average over all, `2`=majority consensus, `3`=MAP, `4`=MCC; `:153`).

### `consensusTree.R` — point estimate from a tree set
Collapses many trees into one and writes it. Same `-m` modes as above (`:137`). `-d/--discard N` drops the first N% as burn-in (`:138`). Used by MP4 (`-m 2`, majority) and GA (`-m 4 --discard 50`, MCC).

### Supporting helpers
- `printQuartets.py` — PCH_W quartets from CSV → stdout (ASTRAL III format; `-w` for wASTRAL weighted format).
- `getResultBipartitions.py` — collect MP4 (`-m`) / GA (`-g`) bipartitions into ASTRAL's constraint-set format.
- `commandLineNex.R` — CSV → NEXUS; `-p/--resolve-poly` polymorphism handling, `-m/--morph-weight` character weight.
- `consensusTree.R`/`RFScorer.R` `-m`: `1`=average, `2`=majority consensus, `3`=MAP, `4`=MCC.
