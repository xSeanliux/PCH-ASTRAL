# CAMUS inference (future work)

`scripts/sh/runCAMUS.sh` is a stub. This is the intended contract for the real
implementation, mirroring `runASTRAL3.sh`.

## Runner contract (already wired)

`CamusRunner` (`scripts/lib/inference/runners/camus.py`) calls:

```
bash scripts/sh/runCAMUS.sh \
  --runid <id> --input <dataset.csv> --name <stem> \
  --output <output_dir> --guide-trees <mp,ga,astral3,true_tree csv>
```

Set CAMUS `-o <output_dir>/CAMUS/networks/<name>`. CAMUS then writes:
- `<name>.csv` — all networks, one row per k (cols: `Number of Branches`,
  `Quartet Satisfied Percent`, `Extended Newick`; row k=0 is the guide tree). This
  IS the network family.
- `<name>.log` — CAMUS's own log.
- `<name>.png` — CAMUS's lineplot (% quartets unsatisfied vs #reticulations).

Note the family breaks `api.infer`'s one-point-estimate readback. The current stub
wiring reuses `CamusRunner.point_estimate_path` (the `<name>.csv` stem); the real
impl enriches that CSV and appends it to `camus_registry.csv` — see `registry.md`.

## What runCAMUS.sh must do

1. **Quartets** — generate gene-tree quartets from the polymorphic CSV. Reuse the
   PCH quartet generation (`scripts/py/printQuartets`, `scripts/lib/pch.py`);
   CAMUS takes gene trees / quartets as its second argument.
2. **Guide tree(s)** — resolve each `--guide-trees` token to a rooted binary
   newick constraint tree:
   - `mp` / `ga` / `astral3` → the upstream method's point estimate under
     `<output_dir>/{MP4,GA,PCH_W_ASTRAL3}/trees/<name>.tree`. These are declared
     dependencies (`CamusRunner.dependencies`), so the scheduler guarantees they
     exist before CAMUS runs.
   - `true_tree` → the simulation model tree. Join `dataset_id` →
     `simulated_data_registry.csv` to find the model tree / network file
     (`net{edges}-{tree}.txt`, `data/README.md`). No dependency.
   - CAMUS needs the constraint tree **rooted + binary**; add rooting/refinement
     if the source tree isn't.
3. **Run CAMUS** — `bin/camus -o <prefix> [-t thresh -n procs] <const_tree>
   <gene_trees>`. It writes `<prefix>.csv` with every k (the sweep is the point);
   the writer ingests that CSV into the registry (`registry.md`).

## Open questions

- One CAMUS run per guide tree, or one guide tree per config? `guide_trees` is a
  list → one output family per guide tree. Simplest first cut: one guide tree per
  `camus:` block.
- Which k / threshold defaults match the paper (btag245 supplement).
