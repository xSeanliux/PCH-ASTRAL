# Join Keys 

The main join keys of this dataset are: 

1. dataset key: they uniquely determine the _tree/network_ from which to simulate things down: 
    - tree number (int)
    - number of lateral transfer / reticulate edges (int), 0 means tree and >= 1 means network. 

2. Simulation config key: uniquely determines _what_ the  configuration is for characters to be simulated down the tree:
    - polymorphism level: (in `verylow`, `low`, `mid`, `high`, `veryhigh`)
    - min tree height (int) 
    - homoplasy factor (float) 
    - no. characters 

3. Dataset config key: uniquely determines each _dataset_ that is used, and each maps to a single CSV file.
    - dataset key 
    - simulation config key 
    - replicate number (int), we use multiple replicates per dataset key & sim config key to reduce variance. 


4. Inference methods: 
    - PCH_W: is a method of getting quartets from a dataset CSV file. We then use a number of _quartet summary methods_ to find the tree maximising satisfied quartets — an NP-hard problem, so each summary method approximates it differently:
        - ASTRAL III: Java, dynamic programming over a constrained set of bipartitions drawn from the input quartets; statistically consistent under the multi-species coalescent. Accepts manual bipartition enhancement sets on top of the automatic ones. (Zhang et al. 2018, BMC Bioinformatics.)
        - ASTRAL IV: C++ reimplementation in the ASTER package. Builds its own search space via greedy placement + NNI refinement, so no manual bipartition set is needed; scales near-linearly in the number of quartets. (Zhang et al. 2025, MBE.)
        - wASTRAL: weighted ASTRAL (ASTER). Each quartet contributes a weight (by gene-tree branch support and/or length) rather than a unit vote, folding quartet uncertainty into the objective. Identical quartets are collapsed and their weights summed, so runtime scales with the number of _unique_ quartets, not the raw count. (Zhang & Mirarab 2022, MBE.)
        - Tree weighted QMC (TREE-QMC): divide-and-conquer on the Quartet Max Cut framework — builds a taxon graph weighted by quartet agreement, takes a max cut to bipartition, and recurses. Offers several quartet normalisation schemes (n0/n1/n2) to correct weight inflation from artificial taxa. (Yan et al. 2023, Genome Research.)
        - TOB-QMC: TREE-QMC's `--blob` mode. Estimates the tree of blobs (each reticulate region contracted to a polytomy) by hypothesis tests on quartet CFs; input for BROOQS/NetCS, not a network or species-tree estimate: ignore its RF scores; not a valid guide tree. (Dai, Han & Molloy 2025, bioRxiv.)
        - NetCS (network): TREE-QMC's `--network` mode. Resolves each blob of degree ≥ 5 in `tob_qmc`'s tree of blobs (a fixed dependency, not a guide tree) into a cycle with one hybrid; smaller blobs stay polytomies. No config fields, no seed: output varies between runs. Point estimate rerooted on the outgroup; when it cannot be, kept as NetCS wrote it and not scored (`docs/method_docs/netcs/README.md`). (bioRxiv 2026.06.06.730607.)
        - CAMUS (network): level-1 network per k maximising PCH-W quartet agreement within a rooted binary guide tree (`guide_trees`, one run each). `camus_bidirectional`: same with CAMUS `-B` (our fork), run names end `.bi`; `edges_added` counts events (`SCHEMAS.md`).
        - SNaQ (network): level-1 network by maximum pseudolikelihood on quartet concordance factors, counted from the PCH-W quartets. Starts from its guide tree (`guide_trees`, one run each, as CAMUS; any tree method but `tob_qmc`, or `true_tree`); hmax = the dataset's true contact event count, as in the CAMUS paper. Quartet CFs are unrooted, so SNaQ's network is semi-directed; the point estimate is its lowest `-loglik` network consistent with the outgroup, rerooted on it; none consistent: no point estimate (`SCHEMAS.md`, family CSV). Julia (`make install-snaq`). (Solís-Lemus & Ané 2016, PLoS Genetics.)
        - BROOQS (network): expands the `tob_qmc` tree of blobs into a level-1 network from the PCH-W quartets: one cycle and one hybrid per blob, so k = the tree's polytomy count, not configurable; a binary tree of blobs comes back unchanged (k = 0). Needs `tob_qmc` enabled and the outgroup, on which the tree of blobs must be rooted. Python, installed by `make setup` (pinned in `pyproject.toml`). (bioRxiv 2026.08.31.748319.)
    - Gray & Atkinson: Bayesian inference over cognate presence/absence characters. Uses MrBayes (MCMC) to sample trees from a posterior distribution, then takes the MCC (maximum clade credibility) tree — the sampled tree maximising the product of its clades' posterior probabilities — as the point estimate. (Gray & Atkinson 2003, Nature.)
    - Maximum Parsimony (MP, MP4): finds the tree(s) minimising total character-state changes. Ties are common, so the majority consensus of the equally-parsimonious trees is the point estimate. MP4 is the best-performing of the MP variants for polymorphic characters in Canby et al. 2024 (Trans. Philological Society). 
    
