# Quartet-based network methods to benchmark against

Can PhyloNet or PhyloNetworks infer networks **from quartets**, the way CAMUS does? Short
answer: **PhyloNet no, SNaQ yes** — and SNaQ fits our pipeline almost exactly.

## PhyloNet — no

Zero quartet classes in `bin/PhyloNet.jar` (3.8.5). Every network-inference command takes
**gene trees** (a NEXUS `TREES` block) or sequences:

`InferNetwork_MP`, `InferNetwork_ML`, `InferNetwork_MPL`, `InferNetwork_ML_BootStrap`,
`InferNetwork_ML_CV`, `InferNetwork_Clustering`, `InferNetwork_NCM`,
`InferNetwork_ParentalTrees`, `MCMC_GT`, `MCMC_SEQ`, `MCMC_BiMarkers`, `MLE_BiMarkers`,
`MLE_SEQ`.

A quartet *is* a 4-taxon tree, so `InferNetwork_MP`/`MPL` could be fed our quartets as if
they were gene trees. But that is not a supported input mode, and the pseudo-likelihood
models assume gene trees generated under the multispecies coalescent — feeding
polymorphism-derived quartets would be using the model outside its assumptions. Treat this
as a possible experiment, not a benchmark.

Note the CAMUS paper's `PhyloNet-MPL` baseline was run on **gene trees**, which we do not
naturally have (our pipeline produces quartets). So it is a poor fit for us regardless.

## SNaQ — yes, and it is the natural head-to-head

`snaq!` estimates a network from **quartet concordance factors** by maximum
pseudo-likelihood, searching the space of **level-1 networks** — the same hypothesis space
as CAMUS. That makes it the right comparison: same inputs, same output class, different
algorithm.

- Now its own package: [`JuliaPhylo/SNaQ.jl`](https://github.com/JuliaPhylo/SNaQ.jl),
  split out of PhyloNetworks.jl. Implements Solís-Lemus & Ané (2016).
- Input reader: `readtableCF(file; delim=',')` — a CSV with **one row per 4-taxon set**:
  four taxon-label columns, then `CF12_34`, `CF13_24`, `CF14_23` (or positionally, columns
  5–7), plus an optional `ngenes` column. `readListQuartets` also exists.
- The CAMUS paper used it as a baseline, deriving CFs with
  `countquartetsintrees` from gene trees, then passing them to SNaQ.

### It plugs straight into PCH-W

We do not need gene trees for this. `PCH_W.get_quartets` already returns a
`Counter[Quartet]` — quartet topology → weight. For each 4-taxon set the three resolutions
carry weights `w1, w2, w3`, so

```
CF_i = w_i / (w1 + w2 + w3)
```

is a direct conversion, roughly 15 lines. `scripts/lib/pch.py` already has a `--format`
switch (`astral3|wastral|qfm`), so this is one more format — `--format cf` — writing the
table `readtableCF` expects. No new concepts, no gene-tree detour.

**The honest caveat:** a concordance factor is defined as the *frequency of a quartet
topology across loci*. PCH-W weights come from polymorphic character data, not locus
counts. Normalising them to sum to 1 makes them CF-shaped, but they are not CFs in the
model's sense, and SNaQ's pseudo-likelihood assumes the MSC generated them. The same
objection applies to CAMUS (which also consumes our weights as if they were gene-tree
counts), so this is a property of the whole quartet-based line of work here rather than a
reason to prefer one method — but it belongs in the paper's limitations, not in a footnote.

## Recommendation

Not part of the five PRs in `PLAN.md`; this is what comes after the elbow works. When a
baseline is wanted, SNaQ is the one to add: identical input shape, identical hypothesis
space, one new `--format cf` writer, and a Julia dependency. Compare on the same
`camus_registry.csv` → `network_scores.csv` path, scoring both with the same `CmpNets`
settings (see `scoring.md`).
