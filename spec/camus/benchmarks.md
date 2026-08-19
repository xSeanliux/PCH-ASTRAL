# Quartet-based network methods to benchmark against

Can PhyloNet or PhyloNetworks infer networks **from quartets**, the way CAMUS does?
**Both can.** PhyloNet takes them as taxon-incomplete gene trees (verified), and SNaQ takes
them as concordance factors. Two usable baselines, both matching CAMUS's inputs.

## PhyloNet — yes, via gene trees (a quartet *is* a taxon-incomplete gene tree)

No PhyloNet command advertises quartet input, and none of its classes mention quartets. But
that framing is a red herring: **a quartet is just a very taxon-incomplete gene tree**,
which is exactly how `runASTRAL3.sh` already feeds PCH-W quartets to ASTRAL. PhyloNet's
gene-tree methods accept them the same way.

Verified by running `bin/PhyloNet.jar` on eight 4-taxon quartets over a 5-taxon label set:

| command | result on quartet input |
|---|---|
| `InferNetwork_MP` | **works**, seconds — returned a 5-taxon network with 1 reticulation |
| `InferNetwork_MPL` | **works** — returns networks ranked by log pseudo-likelihood |
| `InferNetwork_MPL -s <tree> -fs` | **works**, k=1 in 15 s, k=2 in 32 s |
| `InferNetwork_ML` | did **not** finish in 7 min on 5 taxa |

`InferNetwork_ML`'s behaviour matches the paper, which excluded unconstrained PhyloNet-MPL
because it "could not complete within 24 hours". `InferNetwork_Clustering` and
`InferNetwork_NCM` are untested (the ML hang blocked that batch).

### PhyloNet-MPL(FT) is the natural head-to-head with CAMUS

The flags matter and are easy to get wrong: **`-s <id>` only sets the *starting* network and
still searches** — that is what hung my first attempt. **`-fs` (no value) fixes it.** The
paper's "PhyloNet-MPL (FT)" is `-s start -fs`; their wrapper's `-f` maps to `-fs`.

With that, MPL(FT) matches CAMUS's shape almost exactly:

| | CAMUS | PhyloNet-MPL(FT) |
|---|---|---|
| inputs | guide tree + quartets | fixed start tree + quartets (as gene trees) |
| k | discovers every k up to m | you specify k per run |
| output | level-1 networks | networks (not restricted to level-1) |

So sweeping `k = 1..m` gives the *same per-k family* CAMUS produces — the same
`camus_registry.csv` shape, the same `CmpNets` scoring, the same elbow. That makes it a
drop-in baseline, and it is the paper's own primary comparison.

**Runtime is the open question.** 15 s and 32 s at 5 taxa is not reassuring for 30 taxa ×
many k × many replicates; the paper reports MPL(FT) taking hours and failing above 51
species. Benchmark one 30-taxon dataset before committing to a sweep.

## SNaQ — yes, quartet-native and level-1

`snaq!` estimates a network from **quartet concordance factors** by maximum
pseudo-likelihood, searching the space of **level-1 networks** — the same hypothesis space
as CAMUS. Where MPL(FT) matches CAMUS's *interface* (guide tree + k), SNaQ matches its
*output class*: both are restricted to level-1, so neither can represent a non-level-1
truth and the two share the same error floor.

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

Neither is part of the five PRs in `PLAN.md` — this is what comes after the elbow works.
When baselines are wanted, add them in this order:

1. **PhyloNet-MPL(FT)** first. No new dependency (the jar is already installed for
   scoring), it consumes our quartets unchanged, and per-k runs drop straight into the
   existing registry and scorer. It is also the paper's own primary baseline, so the
   comparison is legible to that audience. Settle the runtime question at 30 taxa first.
2. **SNaQ** second. Stronger scientific pairing — same level-1 hypothesis space, so it
   shares CAMUS's error floor and isolates the algorithm rather than the hypothesis class.
   Costs a `--format cf` writer (~15 lines) and a Julia dependency.

Score every method through the same `network_scores.csv` path with identical `CmpNets`
settings (see `scoring.md`), so the numbers are comparable by construction.
