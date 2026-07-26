# Outgroup rooting (future work)

CAMUS requires a **rooted** binary constraint tree and ships no rooting code
(`inference.md`). The PCH methods return unrooted trees, so the root has to come
from somewhere. Guessing post hoc (midpoint) is a modelling assumption we'd rather
not smuggle in; instead **simulate an outgroup** and root on it.

## Config

Experiment-level, under `simulation:` — it changes the generated data, and nothing
outside simulation reads it.

```yaml
simulation:
  n_taxa: 30
  outgroup: OG        # omit entirely for no outgroup
  base_trees_file: data/trees.txt
```

```python
class ExperimentSimulationConfig(BaseModel):
    ...
    outgroup: str | None = Field(None)   # None = no outgroup
```

One optional field, not an `enabled` + `name` pair: absent means off, present
means on with that label, and no inconsistent state is representable.

**Experiment-level is forced, not just tidy.** `registry_key` in
`handle_simulation.py` (poly, chars, height, homoplasy, horizontal_edges,
model_tree, replica) drives both the seed (`stable_hash_dict`) and the output path
`sim_{h}_{treenum}_{replica}.csv`. It has no outgroup term, so two runs of one
experiment folder differing only in outgroup would collide on path — and
`dataset_id` is that path, so the inference registry couldn't separate them
either. One folder, one setting. Adding an outgroup term to `registry_key` (new
column + new seeds) is only worth it if we ever want both in one experiment.

Not recorded as a sim-registry column for now: it's constant per folder and the
yaml is the record. Add the column if cross-folder analysis needs it.

## Mechanism

Graft the outgroup as sister to the whole base tree — `(base, OG)` — so it is by
construction the deepest split, then let the simulator evolve characters along its
branch like any other taxon. `n_taxa: 30` refers to the ingroup; the base trees are
fixed files with `t1..t30`, so the outgroup is additive (31 tips simulated).

**Two code paths.** `handle_simulation.py:197-205` branches on reticulations:

- `horizontal_edges == 0` → the base tree is passed inline as newick
  (`--tree <newick>`). Grafting is string/tree surgery on that newick.
- `horizontal_edges > 0` → a network **file** is passed
  (`--network-input-file net{h}-{t}.txt`). The outgroup has to be added to the
  network format instead, and a rewritten file staged. This is the awkward half.

## Consuming it

`runCAMUS.sh` (and anything else needing a rooted tree):

1. Take the method's unrooted estimate, which now includes the outgroup tip.
2. Root on the outgroup branch → `(OG, (ingroup...))`.
3. **Prune the outgroup.** The root becomes a unifurcation, which CAMUS's own
   `RemoveSingleNodes()` collapses — leaving a rooted binary tree on the original
   30 taxa.

Step 3 matters for comparability: scoring then runs on the same taxon set as every
existing run, so FN/FP stay comparable to pre-outgroup results. Keeping the
outgroup through scoring would instead add one edge that every method should
recover, quietly deflating error rates and breaking comparison with existing
numbers.

## Cost

Changes `ExperimentSimulationConfig` and the base trees/networks, so **cached
simulation data for any experiment that turns this on must be regenerated**.
Existing experiments with `outgroup` absent are untouched.

## Open questions

- **Outgroup branch length / depth.** Too short and its position isn't reliably
  recovered (so rooting is wrong); too long and homoplasy saturates the characters.
  Needs a value, and probably a sensitivity check.
- **Network grafting.** What the `net{h}-{t}.txt` format needs for an extra taxon,
  and whether it's easier to pre-generate outgrouped network files than to rewrite
  them at run time.
- **Does the outgroup's own polymorphism matter?** It's simulated under the same
  character model as the ingroup; worth confirming that's sensible rather than
  giving it its own settings.
- Do the tree methods actually recover the outgroup's position reliably at our
  homoplasy levels? If not, outgroup rooting is no better than midpoint and this
  whole approach needs rethinking. **Check this before building the rest.**
