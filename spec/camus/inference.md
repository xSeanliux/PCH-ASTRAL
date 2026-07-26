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
   - `true_tree` → the simulation's base tree, via the existing
     `scoring.resolve_reference_newick(experiment_folder, model_tree)` (reads
     `model_graph_registry.csv` for the `horizontal_edges == 0` row). No dependency.

   See "The rooted-binary constraint" below — this is the gate on the whole step.
3. **Run CAMUS** — `bin/camus -o <prefix> [-t thresh -n procs] <const_tree>
   <gene_trees>`. It writes `<prefix>.csv` with every k (the sweep is the point);
   the writer ingests that CSV into the registry (`registry.md`).

## The rooted-binary constraint

`prep.Preprocess` **hard-errors** on a constraint tree that isn't rooted, binary,
and duplicate-free (`ErrUnrooted` / `ErrNonBinary` / `ErrMulTree`,
`internal/prep/preprocess.go:31-39`). CAMUS ships **no** refinement or rooting
code — nothing in the source matches `refine|resolve|polytom|multifurc`, and no
flag changes it. `RemoveSingleNodes()` strips degree-2 nodes for free; polytomies
and unrooted inputs are rejected outright.

`TreeIsBinary` requires the root to have exactly 2 neighbours and every internal
node exactly 3.

Measured on `experiments/smoke_test` output (`low_0.1_4_80/sim_0_1_1`):

| guide | root children | multifurcating nodes | CAMUS |
|---|---|---|---|
| `mp` (`{name}-maj.tree`) | 4 | 3 | **rejected** |
| `ga` (MCC) | 3 | 0 | **rejected** (unrooted) |
| `astral3` | 2 | 0 | accepted |
| `true_tree` (base tree) | 2 | 0 | accepted |

`mp` fails structurally, not by luck: its point estimate is a **majority
consensus** (`consensus(trees, p=0.5, rooted=FALSE)` in `scripts/R/consensusTree.R`),
which collapses every bipartition under 50% support — polytomies are what it is
*for*. Real output: `(t21,t28,t23)`, `(t5,t6,t7)`.

**Don't paper over this by auto-resolving polytomies.** Preprocess deletes every
quartet the constraint tree already displays (`preprocess.go:51-57`), so an
invented resolution deletes quartets the data never supported — suppressing
conflicting signal exactly where support was weakest, which is where reticulation
is most plausible. Arbitrary refinement biases CAMUS *away* from finding edges in
the uncertain regions.

**Decisions taken:**

- `mp` and `ga` are **not** allowed guides. `_GUIDE_TREE_DEPENDENCY` in
  `scripts/lib/experiment.py` is the allow-list (absent key = unsupported); a
  `CamusConfig` field validator rejects them at config load with the reason.
- Rooting for the PCH methods (`astral3`, and `w_tree_qmc` when it becomes a
  guide) will be solved **in the simulation: add an outgroup**, so the inferred
  trees can be rooted deterministically instead of guessed at post hoc. This
  changes `ExperimentSimulationConfig` / the base trees and is its own piece of
  work — until it lands, `astral3` is usable only because its output happens to
  come back with a bifurcating root; that is not something to rely on.

## Open questions

- Outgroup mechanics: added to the base trees before simulation, or grafted per
  replicate? Must survive into every method's output to be usable for rooting,
  and must be excluded from scoring.
- One CAMUS run per guide tree, or one guide tree per config? `guide_trees` is a
  list → one output family per guide tree. Simplest first cut: one guide tree per
  `camus:` block.
- Which k / threshold defaults match the paper (btag245 supplement).
