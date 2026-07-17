# Operational Issues

Cluster-scale gotchas hit running the config-driven pipeline on the ICC (SLURM).
Runtime/CLI symptoms are in `CLI.md` § *Troubleshooting*; this file covers the
environment and scaling traps that only show up at full-experiment scale.

## R version ABI break (system R upgraded)

**Symptom:** MP4/GA silently produce no tree; log shows
`rlang.so: undefined symbol: SETLENGTH` (or similar) loading `shiny`/`dplyr`.

**Cause:** the project R library (`$TALLIS/Rlibs`, built under R 4.4.2) fails to
load once the system `/usr/bin/Rscript` is upgraded to a new *minor* version
(4.6.x dropped the `SETLENGTH` non-API symbol). The `R/4.2.3`/`R/4.5.1` modules
are informational stubs — they don't provide an older R binary.

**Fix:** rebuild the deps under the current R into a version-tagged lib and
repoint `scripts/sh/env.sh`:
```bash
lib=$TALLIS/Rlibs-<maj.min>          # e.g. Rlibs-4.6
PATH=/usr/bin:$PATH; unset LIBRARY_PATH CPATH   # see next section
Rscript -e '.libPaths("'"$lib"'"); install.packages(
  c("shiny","optparse","dplyr","stringr","ape","testit","phangorn","castor","TreeDist"),
  lib="'"$lib"'", dependencies=TRUE, Ncpus=8)'
```
Then set `R_LIBS` to that dir first (env.sh derives `../Rlibs-4.6`).

## Rebuilding R packages needs the *system* gcc

**Symptom:** every R package compile dies with
`cc1: fatal error: inaccessible plugin file …/annobin.so … No such file or directory`.

**Cause:** R's `Makeconf` uses RedHat hardening specs (`-specs=…redhat-annobin-cc1`)
that load gcc's `annobin` plugin. `gcc` on `PATH` resolves to the module compiler
(`/sw/apps/gcc/…`), which doesn't ship annobin. The system `/usr/bin/gcc` does
(R itself was built with it).

**Fix:** put `/usr/bin` first on `PATH` for the install, and run from a cwd
*without* a `specs/` subdir (the repo root has one → `gcc: cannot read spec file
'./specs'`). `unset LIBRARY_PATH CPATH` too — empty entries make gcc read `./specs`.

## GA (MrBayes) does not fit the 4 h queue at ≥320 chars

**Symptom:** after a full run, GA is incomplete on every 320/640-char condition
(~55–65%), with jobs `CANCELLED`/`TIMEOUT` at exactly `04:00:00`.

**Cause:** per-dataset runtime scales hard with `n_chars` (measured, 30 taxa):

| method | 80 ch | 320 ch | 640 ch |
|--------|-------|--------|--------|
| MP4 | 5 s | 5 s | 6 s |
| ASTRAL3 | 27 s | 87 s | 187 s |
| **GA** | **72 s** | **188 s** | **334 s** |

The fan-out runs **one job per (condition, method)** over all ~128 datasets
sequentially. GA×128 at 320 chars ≈ 6.7 h > the `secondary` 4 h cap. Requeue-on-
timeout is meant to absorb this, but a single 4 h window only clears ~76 GA
datasets, and requeues accumulate progress **only via `completed_runs`** (registry
∪ shards). If the registry is empty until the final compact — or a *concurrent*
run's compact deletes the shards mid-flight — each requeue effectively restarts,
so GA stalls at ~one window.

**Fix / resume:** the pipeline is idempotent — just resubmit. Once the registry
is compacted (holds prior progress), a fresh fan-out skips done datasets and each
GA job only faces its remainder (~52/condition → fits one window):
```bash
pch experiment inference EXPERIMENT.yaml --executor slurm --astral-mem-gb 128 --resubmits 4
pch experiment status    EXPERIMENT.yaml     # find any remaining gaps
```
Repeat until `status` is clean — each round advances the registry. For the
heaviest conditions (256-dataset, 640-char), one resume may still need a requeue;
the real one-shot fix is smaller per-job dataset chunks (`--datasets FILE`) or a
longer-walltime partition. Don't run two overlapping fan-outs on one experiment
folder: they share `inference_data/shards/` and each other's compact can delete
in-flight shards (safe for data — per-record appends recreate them — but it
defeats requeue accumulation, and both overwrite the fixed `spec.snapshot.yaml`).

## ASTRAL3 heap: one heavy tier for the whole run

**Symptom:** ASTRAL3 OOM on high-`n_chars` conditions; but bumping memory
over-allocates the small ones.

**Cause:** the executor has two tiers (heavy=ASTRAL3, light=MP4/GA), not a
per-condition map. `--astral-mem-gb N` sets *all* ASTRAL3 jobs to `N`.

**Fix:** size for the largest condition. 640 chars runs fine at
`--astral-mem-gb 128` (~108 g heap) on the 192 GB nodes; the default 64 g tier
(~54 g heap) covers ≤320. Per-quartet scaling: ≈ `n_chars × char_weight` weighted
quartets (see `CLI.md` scale note).

## Cluster maintenance reservations block/extend

**Symptom:** submitted jobs sit `PD` with reason
`(ReqNodeNotAvail, Reserved for maintenance)`; partitions show `maint`/`down`.

**Cause:** a SLURM `MAINT` reservation with `ALL_NODES` drains every partition.
End times can be **extended** mid-window (seen: a 00:00 window pushed to 12:00).

**Fix:** none — wait it out. `scontrol show reservation` for the current end time;
`sinfo -o "%P %t %D"` to confirm nodes returned. Jobs run automatically when it
lifts; nothing to resubmit.

## Sourcing / invocation reminders

- **Always `source scripts/sh/env.sh`** before any `pch` command (sets `R_LIBS`,
  `PYTHONPATH`, `PCH_SCRATCH`, ASTRAL heap). A bare shell lacks them → silent
  no-tree failures. Don't wrap it behind `2>/dev/null` in a file that might be
  cleaned up (a vanished wrapper fails silently, leaving a stale `R_LIBS`).
- **`pch` console script hits the `PYTHONPATH` shadow** (another project's
  `scripts/` package) → `ModuleNotFoundError: scripts.py.cli`. Use
  `python -m scripts.py.cli.main …` (cwd wins), or clear `PYTHONPATH`.
- **`pch experiment status` takes the YAML**, not the folder (else
  `IsADirectoryError`). It reads registry ∪ shards, so it's accurate mid-batch —
  the fastest way to see per-condition gaps.
