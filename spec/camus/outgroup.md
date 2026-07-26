# Outgroup rooting (future work)

CAMUS requires a **rooted** binary constraint tree and ships no rooting code
(`inference.md`). The PCH methods return unrooted trees, so the root has to come
from somewhere. Guessing post hoc (midpoint) is a modelling assumption we'd rather
not smuggle in; instead **simulate an outgroup** and root on it.

This is what the CAMUS paper itself does — their pipeline is ASTRAL-IV → reroot on
the outgroup (`root-outgroup.py`, TreeSwift) → CAMUS, and they note CAMUS works
"provided an outgroup is available (which is typically the case)". Our
`astral3` → root → CAMUS plan is the same shape, so we can follow their protocol
rather than invent one.

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
branch like any other taxon. `n_taxa: 30` is the ingroup; the base trees are fixed
files with `t1..t30`, so the outgroup is additive (31 tips simulated).

### It's a root-level wrap, and that makes it cheap

`net{h}-{t}.txt` is **base tree on line 1, then one line per reticulation edge**:

```
((((((t15:0.065,t14:0.0049):0.098,t11:0.076):0.033, ... )        <- base tree, no trailing ';'
t8;((t6:0.0097,t7:0.0101):0.0048,t5:0.0093);0.4502;0.1922        <- source;target;p;p
```

The edge's target is a **verbatim substring of line 1** (verified). Wrapping at the
root only prepends `(` and appends `:len,OG:len)`, so every internal subtree string
survives byte-identical — **the edge lines need no rewriting at all**. Edge counts
match `h` exactly (net1→1, net2→2, net3→3), and the base tree is shared across `h`
for a given tree number.

So one function covers both formats. The only real difference is the terminator:
`trees.txt` lines end with `;`, network line 1 does not — preserve whichever came in.

```python
def graft_outgroup(newick: str, name: str, root_len: float, og_len: float) -> str:
    s = newick.strip()
    term = ";" if s.endswith(";") else ""
    return f"({s.rstrip(';')}:{root_len},{name}:{og_len}){term}"
```

Assert the grafted string still contains each edge target, so a future format change
fails loudly instead of silently producing a network with dangling edges.

### Where it goes

At the **existing copy step**, not at simulation time — `handle_simulation.py` already
writes trees into the experiment folder (`model_tree_{i}.txt`, :48-51) and copies
networks into `model_networks/` (:76-77). Grafting there means one insertion point,
both formats, and `model_graph_registry.csv` + `resolve_reference_newick` pick up the
outgrouped versions for free.

> **Landmine.** `network_registry` records the **source** path
> (`base_networks_dir/net{h}-{t}.txt`, :65-67), not the copy it just made — so today
> the network copies are decorative and simulation reads the originals. Grafting at
> the copy step would therefore have **no effect** for `h > 0` until that path is
> pointed at the copied file. Fix it in the same change (trees already do this
> correctly, so the two paths also stop disagreeing).

### Branch lengths — follow the CAMUS paper

Willson & Warnow (Bioinformatics 2026) do exactly this, and their supplement gives
the numbers. Their `add-outgroup.py` ([gist](https://gist.github.com/jsdoublel/de9ab383e0734d53222e289d0a737870))
is the same root-level wrap:

```python
f"(OUT:{r.uniform(0.9, 1.0)},{ingroup_no_semicolon}:{r.uniform(0.0, 0.1)});"
```

> "a single vertex was created as the root, then the outgroup leaf was added with an
> edge length [0.9, 1.0] (uniform distribution); finally, the previously generated
> network was attached to the other side of the root on the other side of a branch
> with length [0.0, 0.1]." — Supplementary §1.1

So: **outgroup branch `U(0.9, 1.0)`, ingroup stem `U(0.0, 0.1)`**, label `OUT`, fixed
RNG seed for reproducibility. The short stem is the point — the outgroup diverges only
just before the ingroup MRCA, and its long branch simply carries it to the present.

These numbers transfer directly to us: our base trees are normalised to max
root-to-tip `1.0` (min tip depth `0.068`, so not ultrametric), the same scale their
ingroup sits on, which is why `0.9–1.0` lands the outgroup roughly contemporaneous
with the ingroup tips. `tree_height` does not rescale the newick — it scales
`height_factor` in the generated simulator config
(`scripts/lib/simulation/types.py:97-106`) — so one policy works across every
`tree_height`.

Draw both lengths from a **seed derived from the experiment's registry key**, not a
hardcoded `0`, to match how the rest of the pipeline seeds itself.

**The caveat that keeps the calibration below on the table.** Their branch lengths are
tuned for a molecular pipeline (SiPhyNetwork → PhyloCoalSimulations → INDELible under
GTR, giving ~21% gene-tree estimation error). Ours feed LingPhyloSimulator's
polymorphic character model. The *geometry* transfers because the tree scale matches;
what a branch length means for character evolution does not. Adopt their numbers as
the starting point, then verify.

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

- **Verify the paper's lengths hold under our character model.** Start from
  `U(0.9, 1.0)` / `U(0.0, 0.1)` rather than guessing, but confirm it: graft onto one
  base tree, simulate a handful of replicates, and check whether MP4/GA/ASTRAL
  actually place the outgroup as sister to everything else. Too short and its
  position isn't recovered; too long and homoplasy saturates its characters — either
  way the rooting is wrong. **Do this before building the rest.** If none of the
  methods place it reliably at our homoplasy levels, outgroup rooting is no better
  than midpoint and the approach needs rethinking.
- **Do we prune the outgroup before scoring?** The paper appears not to — its
  species counts are n+1 (16, 26, 51, …). Pruning keeps our FN/FP comparable with
  existing tree runs; not pruning matches the paper. A defensible split: prune for
  the tree RF scores, keep it for network scoring.
- **Does the outgroup's own polymorphism matter?** It's simulated under the same
  character model as the ingroup; worth confirming that's sensible rather than giving
  it its own settings.
- Whether to prune the outgroup inside the scorer (one guarded place, keeps every
  method comparable) or in each consumer. Scorer is the obvious first cut.
